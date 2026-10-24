"""`/usage` renders the local log; it never asks a provider."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.custom_command.usage_command import (
    _duration,
    create_usage_commands,
    render_usage,
)
from zrb.llm.history_manager.conversation_naming import with_slug
from zrb.llm.usage_log import record_usage
from zrb.util.string.name import get_random_name

NOW = datetime.now(timezone.utc)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


@pytest.fixture
def command():
    (only,) = create_usage_commands()
    return only


class _FakeUI:
    """The parts of a UI `/usage` touches: the session name and the panel."""

    def __init__(self, session: str = "") -> None:
        self.conversation_session_name = session
        self.panels: list[tuple[str, str]] = []
        self.outputs: list[str] = []

    def show_panel(self, title: str, body: str) -> None:
        self.panels.append((title, body))

    def append_to_output(self, text: str) -> None:
        self.outputs.append(text)

    @property
    def body(self) -> str:
        """What the UI was asked to show."""
        (_, body), *rest = self.panels
        return body


def _record(
    *,
    model: str = "test-model",
    session: str = "",
    when: datetime = NOW,
    duration_ms: int = 0,
    **counts,
):
    usage = RunUsage(**{"input_tokens": 1000, **counts})
    return record_usage(
        usage, model=model, session=session, when=when, duration_ms=duration_ms
    )


def test_it_is_registered_under_the_configured_alias(command):
    assert command.command == "/usage"
    assert command.args == ["period"]


def test_an_empty_window_says_so(usage_dir, command):
    assert "No usage recorded" in command.handle({}, None)


def test_a_run_appears_under_its_model(usage_dir, command):
    _record(model="openai-chat:gpt-4o", input_tokens=1200, output_tokens=340)

    output = command.handle({}, None)

    assert "openai-chat:gpt-4o" in output
    assert "1.2k" in output


def test_the_cache_line_reports_the_share_served_from_cache(usage_dir, command):
    _record(input_tokens=1000, cache_read_tokens=940)

    output = command.handle({}, None)

    assert "94% of input tokens came from the prompt cache" in output


def test_an_unpriced_run_is_shown_as_unknown_rather_than_free(usage_dir, command):
    _record(model="ollama:local", cost=None)

    output = command.handle({}, None)

    assert "—" in output
    assert "unpriced — their cost is unknown, not zero" in output


def test_a_fully_priced_run_shows_its_cost_without_a_mark(usage_dir, command):
    _record(cost=0.55)

    output = command.handle({}, None)

    assert "$0.55" in output
    assert "$0.55*" not in output


def test_a_partly_priced_model_is_marked(usage_dir, command):
    _record(model="mixed", cost=0.45)
    _record(model="mixed", cost=None)

    output = command.handle({}, None)

    assert "$0.45*" in output


def test_the_default_window_accumulates_every_recorded_run(usage_dir, command):
    """`/usage` answers "what have I spent", not only "what did this chat
    spend": an older run in another conversation is still counted."""
    _record(session="earlier-chat", model="from-yesterday", when=NOW - timedelta(days=3))
    _record(session="now-chat", model="from-now")

    ui = _FakeUI("now-chat")
    command.handle({}, ui)

    assert "every recorded run" in ui.body
    assert "from-yesterday" in ui.body
    assert "from-now" in ui.body


def test_the_session_window_follows_the_ui_session_name(usage_dir, command):
    _record(session="wanted", model="mine")
    _record(session="other", model="theirs")

    ui = _FakeUI("wanted")
    command.handle({"period": "session"}, ui)

    assert "session wanted" in ui.body
    assert "mine" in ui.body
    assert "theirs" not in ui.body


def test_the_session_window_survives_the_automatic_rename(usage_dir, command):
    """A conversation is renamed after its first turn; the first turn's usage
    must not fall out of its own total."""
    name = get_random_name()
    _record(session=name, model="first-turn")
    _record(session="an-unrelated-chat", model="someone-else")

    ui = _FakeUI(with_slug(name, "topic"))
    command.handle({"period": "session"}, ui)

    assert "first-turn" in ui.body
    assert "someone-else" not in ui.body


def test_the_reply_is_drawn_in_a_panel(usage_dir, command):
    """A table in the transcript scrolls away with the next turn."""
    _record()

    ui = _FakeUI()
    reply = command.handle({}, ui)

    assert reply == ""
    assert ui.panels[0][0] == "Usage"
    assert ui.outputs == []


def test_without_a_session_name_the_session_window_falls_back_to_today(
    usage_dir, command
):
    _record(model="today-model")

    output = command.handle({"period": "session"}, None)

    assert "today" in output
    assert "today-model" in output


def test_the_week_window_leaves_older_runs_out(usage_dir, command):
    _record(model="recent", when=NOW - timedelta(days=2))
    _record(model="ancient", when=NOW - timedelta(days=30))

    output = command.handle({"period": "week"}, None)

    assert "recent" in output
    assert "ancient" not in output


def test_all_reads_everything(usage_dir, command):
    _record(model="ancient", when=NOW - timedelta(days=200))

    output = command.handle({"period": "all"}, None)

    assert "ancient" in output
    assert "every recorded run" in output


def test_an_unknown_period_lists_the_valid_ones(usage_dir, command):
    output = command.handle({"period": "yesterday"}, None)

    assert "session, today, week, all" in output


def test_unmeasured_requests_are_called_out(usage_dir, command):
    _record(unmeasured_requests=2)

    output = command.handle({}, None)

    assert "2 request(s) reported no usage" in output


def test_wall_time_is_summed_across_runs(usage_dir, command):
    _record(duration_ms=60_000)
    _record(duration_ms=30_000)

    assert "1m 30s of wall time" in command.handle({}, None)


def test_the_longest_models_are_listed_first(usage_dir, command):
    _record(model="small", input_tokens=10)
    _record(model="large", input_tokens=900_000)

    output = command.handle({}, None)

    assert output.index("large") < output.index("small")


@pytest.mark.parametrize(
    ("milliseconds", "expected"),
    [(500, "0s"), (45_000, "45s"), (90_000, "1m 30s"), (3_900_000, "1h 5m")],
)
def test_durations_read_as_durations(milliseconds, expected):
    assert _duration(milliseconds) == expected


def test_render_is_quiet_about_a_window_with_no_records():
    assert render_usage([], "nowhere") == "  No usage recorded for nowhere."
