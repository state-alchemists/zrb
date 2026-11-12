"""`/usage` adds one line when resuming this conversation is expensive.

The line is the only part of `/usage` that describes the next turn rather than
the last one: a large history left idle long enough for the prompt cache to
lapse is re-sent whole, and a new session costs only its own prompt.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.custom_command.usage.command import _idle, create_usage_commands
from zrb.llm.custom_command.usage.resume import (
    FRESH_SESSION_TOKENS,
    _to_datetime,
    read_resume,
)
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.shared.usage_log import KIND_SUMMARIZATION, record_usage

# A history well over the default `LLM_UI_USAGE_RESUME_HISTORY_TOKENS`: both of
# the limiter's counters (char/4, and tiktoken when it is on) put this above
# 100k tokens, so the test does not depend on which one is enabled.
_LARGE_TEXT = "lorem ipsum dolor sit amet " * 60_000
_SMALL_TEXT = "one short answer"


class _FakeUI:
    """The parts of a UI `/usage` touches: its session, its history, its panel."""

    display = input = tools = property(lambda self: self)
    session = property(lambda self: self)

    def __init__(
        self,
        session: str = "chat",
        history_manager: FileHistoryManager | None = None,
        turn_running: bool = False,
    ) -> None:
        self.conversation_session_name = session
        self.history_manager = history_manager
        self.is_turn_running = turn_running
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


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    # A store path that does not exist, so the Memory section cannot read the
    # developer's own store through this test.
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    return tmp_path


@pytest.fixture
def command():
    (only,) = create_usage_commands()
    return only


@pytest.fixture
def history(tmp_path):
    return FileHistoryManager(history_dir=str(tmp_path / "history"))


def _write_turn(
    manager: FileHistoryManager,
    *,
    ago: timedelta,
    text: str,
    name: str = "chat",
) -> None:
    """Save one finished turn whose messages are stamped *ago*."""
    when = datetime.now(timezone.utc) - ago
    manager.update(
        name,
        [
            ModelRequest(parts=[UserPromptPart(content="hello", timestamp=when)]),
            ModelResponse(parts=[TextPart(content=text)], timestamp=when),
        ],
    )
    manager.save(name, write_backup=False)


def _record() -> None:
    record_usage(
        RunUsage(input_tokens=1000, requests=1),
        model="test-model",
        when=datetime.now(timezone.utc),
    )


def _shown(command, ui, period: str = "") -> str:
    """The panel body `/usage` drew on *ui*.

    Read from the UI, not from `handle`'s return value: a reply drawn in a panel
    comes back as an empty string by design, so asserting on the return value
    would pass whatever the command printed.
    """
    command.handle({"period": period}, ui)
    return ui.body


def test_a_large_stale_history_is_told_what_resuming_costs(usage_dir, command, history):
    _write_turn(history, ago=timedelta(hours=2, minutes=7), text=_LARGE_TEXT)
    _record()

    shown = _shown(command, _FakeUI(history_manager=history))

    assert "last turn 2h 7m ago" in shown
    assert "tokens of history" in shown
    assert "fresh to resume vs" in shown
    assert "to start over" in shown


def test_the_line_sits_under_the_footer_of_the_table(usage_dir, command, history):
    """A `/usage` typed after a break is asking whether to continue: the answer
    belongs above the per-tool and per-store detail, not after it."""
    _write_turn(history, ago=timedelta(hours=3), text=_LARGE_TEXT)
    _record()

    shown = _shown(command, _FakeUI(history_manager=history))

    assert shown.index("runs") < shown.index("resume")


def test_a_recent_turn_gets_no_line(usage_dir, command, history):
    """A pause is not a gap: the cache almost certainly still holds the prefix."""
    _write_turn(history, ago=timedelta(minutes=1), text=_LARGE_TEXT)

    assert "resume" not in _shown(command, _FakeUI(history_manager=history))


def test_a_small_history_gets_no_line(usage_dir, command, history):
    """Below the size threshold, picking the thread back up costs about what a
    new session costs, so warning about it would be noise."""
    _write_turn(history, ago=timedelta(hours=5), text=_SMALL_TEXT)

    assert "resume" not in _shown(command, _FakeUI(history_manager=history))


def test_a_fresh_session_gets_no_line(usage_dir, command, history):
    shown = _shown(command, _FakeUI(history_manager=history))

    assert "resume" not in shown
    # Asking the question must not answer it by creating the history it asks about.
    assert not (usage_dir / "history" / "chat.json").exists()


def test_a_running_turn_gets_no_line(usage_dir, command, history):
    """A live turn is not a resume: the history is in use, not waiting."""
    _write_turn(history, ago=timedelta(hours=3), text=_LARGE_TEXT)
    ui = _FakeUI(history_manager=history, turn_running=True)

    assert "resume" not in _shown(command, ui)


def test_a_trailing_message_with_no_timestamp_does_not_hide_the_gap(usage_dir, history):
    """A failed run saves the error as a further request, and a `ModelRequest`
    carries no timestamp of its own: the turn still ended at the response before
    it, which is what the gap must be measured from."""
    _write_turn(history, ago=timedelta(hours=2), text=_LARGE_TEXT)
    messages = history.load("chat")
    messages.append(ModelRequest(parts=[UserPromptPart(content="[SYSTEM] Error")]))
    history.update("chat", messages)

    reading = read_resume(_FakeUI(history_manager=history))

    assert reading is not None
    assert reading.idle_seconds >= timedelta(hours=2).total_seconds()


def test_a_window_with_no_runs_still_reports_the_line(usage_dir, command, history):
    """The line describes the session, not the window: a `today` window read
    after midnight holds no run and is exactly when the question is asked."""
    _write_turn(history, ago=timedelta(hours=4), text=_LARGE_TEXT)

    shown = _shown(command, _FakeUI(history_manager=history), period="today")

    assert "No usage recorded for today." in shown
    assert "resume" in shown


def test_a_window_that_only_compacted_still_reports_the_line(
    usage_dir, command, history
):
    """A compaction-only window is the most likely one to hold a large history:
    the line follows the table block, not the turns in it."""
    _write_turn(history, ago=timedelta(hours=4), text=_LARGE_TEXT)
    record_usage(
        RunUsage(input_tokens=7_000, requests=1),
        model="small-model",
        kind=KIND_SUMMARIZATION,
        when=datetime.now(timezone.utc),
    )

    shown = _shown(command, _FakeUI(history_manager=history))

    assert "No turn recorded for this window." in shown
    assert "resume" in shown


@pytest.mark.parametrize(
    ("knob", "default"),
    [
        ("LLM_UI_USAGE_RESUME_GAP_SECONDS", 1200),
        ("LLM_UI_USAGE_RESUME_HISTORY_TOKENS", 100_000),
    ],
)
def test_either_knob_at_zero_turns_the_line_off(
    usage_dir, command, history, monkeypatch, knob, default
):
    _write_turn(history, ago=timedelta(hours=3), text=_LARGE_TEXT)
    assert getattr(CFG, knob) == default
    monkeypatch.setattr(CFG, knob, 0, raising=False)

    assert "resume" not in _shown(command, _FakeUI(history_manager=history))


def test_both_thresholds_are_settable(usage_dir, command, history, monkeypatch):
    """The pair that defaults to quiet still fires when a user asks it to."""
    _write_turn(history, ago=timedelta(minutes=2), text=_SMALL_TEXT)
    quiet = _FakeUI(history_manager=history)
    assert "resume" not in _shown(command, quiet)

    monkeypatch.setattr(CFG, "LLM_UI_USAGE_RESUME_GAP_SECONDS", 60, raising=False)
    monkeypatch.setattr(CFG, "LLM_UI_USAGE_RESUME_HISTORY_TOKENS", 1, raising=False)

    shown = _shown(command, _FakeUI(history_manager=history))

    assert "resume" in shown
    assert "last turn 2m ago" in shown


def test_the_resume_figure_is_the_whole_history(usage_dir, command, history):
    """A lapsed cache re-sends the history, so the estimate is the history's own
    size — not a share of it, and not a second measurement of the same thing."""
    _write_turn(history, ago=timedelta(hours=3), text=_LARGE_TEXT)

    reading = read_resume(_FakeUI(history_manager=history))
    shown = _shown(command, _FakeUI(history_manager=history))

    assert reading is not None
    assert reading.history_tokens > CFG.LLM_UI_USAGE_RESUME_HISTORY_TOKENS
    history_figure = f"{reading.history_tokens / 1000:.1f}k tokens of history"
    assert history_figure in shown
    assert f"~{reading.history_tokens / 1000:.1f}k fresh to resume" in shown


def test_the_estimate_names_a_cost_a_new_session_does_not_have(usage_dir, history):
    """The comparison is the point of the line: the same history against what a
    fresh session pays before the first word."""
    _write_turn(history, ago=timedelta(hours=3), text=_LARGE_TEXT)

    reading = read_resume(_FakeUI(history_manager=history))

    assert reading is not None
    assert reading.history_tokens > FRESH_SESSION_TOKENS


def test_without_a_session_there_is_nothing_to_read():
    """A headless run names no conversation, so it has no history to resume."""
    assert read_resume(None) is None


def test_a_conversation_without_a_history_manager_gets_no_line():
    assert read_resume(_FakeUI(history_manager=None)) is None


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        (
            datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc),
            "2026-11-12T10:00:00+00:00",
        ),
        # A naive stamp is read as UTC, never as local time.
        (datetime(2026, 11, 12, 10, 0), "2026-11-12T10:00:00+00:00"),
        ("2026-11-12T10:00:00Z", "2026-11-12T10:00:00+00:00"),
        (None, None),
        ("not a timestamp", None),
        (17, None),
    ],
)
def test_a_message_timestamp_reads_as_an_aware_datetime(stamp, expected):
    parsed = _to_datetime(stamp)

    assert (parsed.isoformat() if parsed else None) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(30, "30s"), (90, "1m"), (3_900, "1h 5m"), (7_200, "2h"), (0, "0s")],
)
def test_a_gap_reads_coarsely(seconds, expected):
    assert _idle(seconds) == expected
