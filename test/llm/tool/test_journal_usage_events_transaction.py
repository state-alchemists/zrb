"""Inside `journal_transaction` an event waits for the commit, and a rollback drops it."""

import pytest

from zrb.config.config import CFG
from zrb.llm.ambient_state import set_current_tool_session
from zrb.llm.journal_usage_log import (
    DELETED,
    SUPERSEDED,
    WRITTEN,
    note_hash,
    read_events,
)
from zrb.llm.tool.journal_write import (
    journal_transaction,
    supersede_journal_note,
    write_journal_note,
)

FIELDS = dict(context="c", finding="f", source="s", hud_line="a line")


@pytest.fixture
def journal(tmp_path, monkeypatch):
    root = tmp_path / "notes"
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_DIR", str(root), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_GIT_ENABLED", False, raising=False)
    return root


def _kinds():
    return [(event.event, event.note) for event in read_events()]


def test_each_transaction_change_records_exactly_one_event_in_order(journal):
    with journal_transaction() as tx:
        tx.write_note("technical", "a", title="A", **FIELDS)
        tx.write_note("technical", "b", title="B", **FIELDS)
        tx.supersede_note("technical", "a", "stale")
        tx.delete_note("technical", "b")

    assert _kinds() == [
        (WRITTEN, note_hash("technical/a")),
        (WRITTEN, note_hash("technical/b")),
        (SUPERSEDED, note_hash("technical/a")),
        (DELETED, note_hash("technical/b")),
    ]


def test_events_are_not_recorded_until_the_body_returns(journal):
    with journal_transaction() as tx:
        tx.write_note("technical", "a", title="A", **FIELDS)

        assert read_events() == []

    assert len(read_events()) == 1


def test_a_failed_transaction_leaves_no_event_and_restores_the_note(journal):
    with pytest.raises(RuntimeError):
        with journal_transaction() as tx:
            tx.write_note("technical", "a", title="A", **FIELDS)
            write_journal_note(category="technical", slug="b", title="B", **FIELDS)
            raise RuntimeError("boom")

    assert read_events() == []
    assert not (journal / "technical" / "a.md").exists()
    assert not (journal / "technical" / "b.md").exists()


def test_a_public_tool_inside_a_transaction_queues_until_commit(journal):
    with journal_transaction():
        write_journal_note(category="technical", slug="a", title="A", **FIELDS)
        assert read_events() == []
        supersede_journal_note("technical", "a", "stale")

    assert _kinds() == [
        (WRITTEN, note_hash("technical/a")),
        (SUPERSEDED, note_hash("technical/a")),
    ]


def test_a_tool_outside_a_transaction_records_immediately(journal):
    write_journal_note(category="technical", slug="a", title="A", **FIELDS)

    assert _kinds() == [(WRITTEN, note_hash("technical/a"))]


def test_a_flush_happens_once_and_a_later_rollback_does_not_replay_it(journal):
    with journal_transaction() as tx:
        tx.write_note("technical", "a", title="A", **FIELDS)
    with pytest.raises(RuntimeError):
        with journal_transaction():
            raise RuntimeError("boom")

    assert len(read_events()) == 1


def test_flushed_events_carry_the_session_of_the_transaction(journal):
    try:
        set_current_tool_session("calm-gate-1234-topic")
        with journal_transaction() as tx:
            tx.write_note("technical", "a", title="A", **FIELDS)
    finally:
        set_current_tool_session("default")

    (event,) = read_events(session_key="calm-gate-1234")
    assert event.event == WRITTEN
