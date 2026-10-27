"""The journal event log: hashed ids, monthly files, tolerant reads."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from zrb.config.config import CFG
from zrb.llm.ambient_state import set_current_tool_session
from zrb.llm.journal_usage_log import (
    INJECTED,
    JUDGED,
    JUDGING,
    SEARCHED,
    JournalEvent,
    note_hash,
    note_id_of,
    read_events,
    record_injected,
    record_judged,
    record_judging,
    record_note_event,
    record_searched,
)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


def _files(usage_dir):
    return sorted(path.name for path in usage_dir.glob("journal-*.jsonl"))


def test_events_round_trip_through_a_monthly_file(usage_dir):
    record_injected(1500, ["technical/a.md", "user/b.md"], True)
    record_searched("two words", ["technical/a.md", "technical/index.md"], 2)

    injected, searched = read_events()

    assert injected.event == INJECTED
    assert (injected.size, injected.truncated) == (1500, True)
    assert injected.hud == [note_hash("technical/a"), note_hash("user/b")]
    assert searched.event == SEARCHED
    assert (searched.terms, searched.results) == (2, 2)
    assert searched.hits == [note_hash("technical/a")]
    (name,) = _files(usage_dir)
    assert name == f"journal-{datetime.now(timezone.utc):%Y-%m}.jsonl"


def test_the_usage_log_does_not_read_the_journal_file_or_the_reverse(usage_dir):
    record_note_event("written", "technical", "a")

    from zrb.llm.usage_log import read_records

    assert read_records() == []


def test_the_hash_is_short_stable_and_hides_the_name():
    first = note_hash("technical/prebuffer")

    assert first == note_hash("technical/prebuffer")
    assert len(first) == 10
    assert "prebuffer" not in first


def test_only_a_category_slug_path_is_a_note():
    assert note_id_of("technical/a.md") == "technical/a"
    assert note_id_of("technical/index.md") is None
    assert note_id_of("index.md") is None
    assert note_id_of("activity-log/a.md") is None
    assert note_id_of("technical/deep/a.md") is None
    assert note_id_of("technical/a.txt") is None


def test_an_unreadable_or_unknown_line_is_skipped(usage_dir):
    record_note_event("written", "technical", "a")
    (path,) = usage_dir.glob("journal-*.jsonl")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("{not json\n")
        handle.write(json.dumps({"timestamp": "x", "event": "written"}) + "\n")
        handle.write(
            json.dumps(
                {"timestamp": datetime.now(timezone.utc).isoformat(), "event": "??"}
            )
            + "\n"
        )

    assert len(read_events()) == 1


def test_a_line_with_malformed_optional_fields_still_reads(usage_dir):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "injected",
        "size": "big",
        "hud": "nope",
    }
    path = usage_dir / f"journal-{datetime.now(timezone.utc):%Y-%m}.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    (event,) = read_events()

    assert (event.size, event.hud) == (0, [])


def test_the_window_and_the_session_select_events(usage_dir):
    try:
        set_current_tool_session("calm-gate-1234-topic")
        record_note_event("written", "technical", "a")
        set_current_tool_session("other-session-5678")
        record_note_event("written", "technical", "b")
    finally:
        set_current_tool_session("default")

    future = datetime.now(timezone.utc) + timedelta(hours=1)

    assert len(read_events()) == 2
    assert read_events(since=future) == []
    (mine,) = read_events(session_key="calm-gate-1234")
    assert mine.note == note_hash("technical/a")


def test_an_unwritable_directory_does_not_raise(usage_dir):
    blocked = usage_dir / "file"
    blocked.write_text("x")
    CFG.LLM_USAGE_DIR = str(blocked)  # restored by the fixture's monkeypatch

    record_injected(1, [], False)
    record_searched("q", [], 0)
    record_note_event("deleted", "user", "x")

    assert read_events() == []


def test_a_judge_run_records_both_ends(usage_dir):
    record_judging()
    record_judged(tool_calls=2, failed=False)

    dispatched, finished = read_events()

    assert dispatched.event == JUDGING
    assert (finished.event, finished.tool_calls, finished.failed) == (
        JUDGED,
        2,
        False,
    )


def test_a_zero_result_search_says_so():
    event = JournalEvent(
        timestamp=datetime.now(timezone.utc), session="", event="searched"
    )

    assert event.is_zero_result
