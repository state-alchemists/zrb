"""`/usage` gains Tools and Journal sections, and omits them without data."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.custom_command.usage_command import create_usage_commands, render_usage
from zrb.llm.custom_command.usage_command_journal import (
    get_note_titles,
    render_journal_section,
)
from zrb.llm.journal_usage_log import (
    DELETED,
    INJECTED,
    READ,
    SEARCHED,
    SUPERSEDED,
    WRITTEN,
    JournalEvent,
    note_hash,
    read_events,
    record_injected,
    record_note_event,
)
from zrb.llm.usage_log import record_usage

NOW = datetime.now(timezone.utc)
A, B, C = (note_hash(f"technical/{name}") for name in "abc")


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_DIR", str(tmp_path / "notes"), raising=False)
    return tmp_path


def _event(kind: str, seconds: int = 0, session: str = "s", **fields):
    return JournalEvent(
        timestamp=NOW + timedelta(seconds=seconds),
        session=session,
        event=kind,
        **fields,
    )


def _record(**kwargs):
    return record_usage(
        RunUsage(input_tokens=1000, requests=1), model="m", when=NOW, **kwargs
    )


def test_the_tools_section_ranks_calls_and_lists_the_idle_registered_tools(usage_dir):
    records = [
        _record(tool_counts={"Read": 5, "Shell": 2}, tool_errors={"Shell": 1}),
        _record(tool_counts={"Read": 1}),
    ]

    out = render_usage(
        records, "label", registered_tools=["Read", "Shell", "Grep", "Glob"]
    )

    assert out.index("Read") < out.index("Shell")
    assert "6 call(s)" in out
    assert "never called (2 of 4 registered on this machine): Glob, Grep" in out


def test_the_tools_section_shows_error_counts_and_caps_the_idle_list(usage_dir):
    record = _record(tool_counts={"Shell": 4}, tool_errors={"Shell": 2})
    idle = [f"Tool{n:02}" for n in range(20)]

    out = render_usage([record], "label", registered_tools=["Shell", *idle])

    assert "4 call(s)  2 error(s)" in out
    assert "Tool11, +8 more" in out


def test_without_counted_tools_the_section_is_omitted(usage_dir):
    out = render_usage([_record()], "label", registered_tools=["Read"])

    assert "Tools" not in out
    assert "never called" not in out


def test_the_journal_section_reports_cost_search_quality_and_note_reuse():
    events = [
        _event(INJECTED, 0, size=2048, hud=[A, B]),
        _event(INJECTED, 1, size=1024, truncated=True, hud=[A, B]),
        _event(SEARCHED, 2, results=0),
        _event(SEARCHED, 3, results=2, hits=[A]),
        _event(READ, 4, note=C),
        _event(SEARCHED, 5, results=1, hits=[A]),
        _event(WRITTEN, 6, note=B),
        _event(WRITTEN, 7, note=C),
        _event(READ, 8, note=C),
        _event(SUPERSEDED, 9, note=B),
        _event(DELETED, 10, note=A),
    ]

    lines = render_journal_section(events, {A: "Alpha", B: "Beta"})
    text = "\n".join(lines)

    assert "1.5 kB per injection on average over 2 injection(s) · 50% truncated" in text
    assert "3 search(es) · 33% found nothing · 1 reworded straight away" in text
    assert "2 written · 1 of them read again · 1 superseded · 1 deleted" in text
    assert "1 of 2 injected note(s) never read or searched for: Beta" in text


def test_a_reworded_search_must_be_followed_in_the_same_session():
    events = [
        _event(SEARCHED, 0, session="one", results=0),
        _event(SEARCHED, 1, session="two", results=0),
        _event(READ, 2, session="one", note=A),
        _event(SEARCHED, 3, session="one", results=1),
    ]

    text = "\n".join(render_journal_section(events, {}))

    assert "0 reworded" in text


def test_unread_hud_notes_are_capped_and_a_missing_note_is_removed():
    hud = [note_hash(f"technical/n{n}") for n in range(8)]
    titles = {hud[0]: "Kept title", hud[1]: "x" * 80}  # long titles are cut
    events = [_event(INJECTED, size=10, hud=hud)]

    text = "\n".join(render_journal_section(events, titles))

    assert "8 of 8 injected note(s) never read or searched for" in text
    assert "+3 more" in text


def test_a_note_that_is_gone_from_the_journal_reads_as_removed(usage_dir):
    record_injected(10, ["technical/gone.md"], False)
    (event,) = read_events()

    text = "\n".join(render_journal_section([event]))

    assert "never read or searched for: (removed)" in text


def test_titles_are_resolved_from_the_current_journal_by_hash(usage_dir, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_JOURNAL_GIT_ENABLED", False, raising=False)
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="a",
        title="Alpha note",
        context="c",
        finding="f",
        source="s",
        hud_line="alpha",
    )

    assert get_note_titles() == {A: "Alpha note"}


def test_a_window_without_events_has_no_journal_section():
    assert render_journal_section([]) == []
    assert render_journal_section([_event(INJECTED, size=1)])[0] == "  Journal"


def test_the_command_prints_both_sections_after_the_table(usage_dir):
    _record(tool_counts={"Read": 3})
    record_injected(2048, [], False)
    record_note_event(WRITTEN, "technical", "a")
    (command,) = create_usage_commands()

    out = command.handle({}, None)

    assert out.index("model") < out.index("  Tools") < out.index("  Journal")
    assert "1 written" in out


def test_the_command_omits_the_sections_when_the_logs_hold_nothing_for_them(
    usage_dir,
):
    _record()
    (command,) = create_usage_commands()

    out = command.handle({}, None)

    assert "  Tools" not in out
    assert "  Journal" not in out


def test_the_period_argument_bounds_the_journal_events(usage_dir):
    _record(tool_counts={"Read": 1})
    record_note_event(WRITTEN, "technical", "a")
    (command,) = create_usage_commands()

    assert "  Journal" in command.handle({"period": "today"}, None)
    ui = _Ui("never-used")
    command.handle({"period": "session"}, ui)
    assert "  Journal" not in ui.shown


class _Ui:
    def __init__(self, session: str) -> None:
        self.conversation_session_name = session
        self.shown = ""

    def show_panel(self, title: str, body: str) -> None:
        self.shown = body
