"""The note the memory reviewer is handed: the date, the hour, the room left."""

import re
from datetime import datetime

import pytest

from zrb.config.config import CFG
from zrb.llm.capabilities.hook.builtin.memory_reviewer import (
    _DAY_APPEND_RESERVE,
    _day_note,
    build_completed_log_hook_config,
    build_memory_reviewer_hook_config,
)
from zrb.llm.capabilities.hook.contracts.interface import HookContext
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.contracts.memory import paths, store
from zrb.llm.contracts.memory.model import KIND_DIARY, Diary, compact_at, digest_body


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_REVIEWER_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def test_a_day_with_room_is_measured_but_not_handed_over(store_dir):
    """The room is stated every turn; the body is paid for only when it is tight.

    A reserve is a guess, and a paragraph can be longer than what is left while
    the page still looks comfortable — so the reviewer gets the measurement every
    turn and the page itself only when it is nearly full.
    """
    body = "Wrote it down."
    store.save_diary(Diary(id=store.today(), claim="A day.", body=body))

    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))

    assert store.today() in note
    assert body not in note
    assert "remain" in note


def test_the_note_carries_the_clock_so_a_paragraph_cannot_lend_itself_one(store_dir):
    """A date and no hour is a reviewer writing night into a morning.

    On 2026-11-18 three paragraphs about events between six and seven in the
    morning said "late in the morning", "late in the evening" and "late in the
    night": the transcript's last turn ended a conversation, and an ending reads
    as night to a model that cannot check. The hour is stated so the guess stops.

    Stated as whose hour it is, because the wording that followed made it worse in
    the other direction. Told that the clock was the review's and not the moment's,
    the reviewer stopped naming hours at all: nothing written on 2026-11-16, 11-19
    or 11-20 names one, and a day without hours loses the order of an argument. The
    note now dates the turn rather than reading out a clock.
    """
    store.save_diary(Diary(id=store.today(), claim="A day.", body="Wrote it down."))

    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))

    assert re.search(r"the turn just ended at \d{2}:\d{2}\b", note)


def test_the_day_and_the_hour_come_from_one_read_of_the_clock(store_dir, monkeypatch):
    """Two reads can straddle midnight: yesterday's date beside today's hour.

    The reviewer is told the day so it can name it in `Remember`, and told the hour
    so it does not invent one. Read separately they can disagree, and a midnight
    turn lands under the wrong date — so both come from one instant.
    """
    reads = []

    class _Midnight:
        @staticmethod
        def now(tz=None):
            reads.append(1)
            return datetime(2026, 11, 18, 0, 0, 1)

    monkeypatch.setattr(
        "zrb.llm.capabilities.hook.builtin.memory_reviewer.datetime", _Midnight
    )

    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))

    assert len(reads) == 1
    assert "2026-11-18" in note
    assert "00:00" in note


def test_a_full_day_is_handed_over_with_the_call_that_makes_room(store_dir):
    """A page that is full refuses the append, and the reviewer cannot see why.

    The reviewer holds one turn's transcript, so an append that comes back refused
    is indistinguishable from a day that did not change. On 2026-11-17 the body
    reached 7,962 of 8,000 characters at half past ten and every paragraph after
    that was lost, which is the failure handing the page over prevents.
    """
    limit = CFG.LLM_MEMORY_DIARY_MAX_CHARS
    body = "x" * (limit - 100)
    day = store.today()
    store.save_diary(Diary(id=day, claim="A long day.", body=body))

    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))

    assert f"{len(body)} of {limit}" in note
    assert body in note
    assert f'Remember(id="{day}", kind="diary", body_mode="w"' in note
    # The digest is what makes the rewrite refusable: two reviewers reading the
    # same day would otherwise each write their own copy over the other's.
    assert f'body_digest="{digest_body(body)}"' in note
    # A day that already has a sentence keeps it: the page is being shortened,
    # not re-titled from one turn's transcript.
    assert "Omit `claim`" in note


def test_a_day_at_exactly_the_reserve_is_handed_over(store_dir):
    """A paragraph can outrun the reserve, so the boundary gives the page away.

    At exactly 600 characters below the point where the day is compacted, a
    601-character paragraph would cross it and be refused; the note used to stop
    one character short of handing the day over, and the reviewer was left with a
    refusal and no page to shorten.
    """
    body = "x" * (compact_at(KIND_DIARY) - _DAY_APPEND_RESERVE)
    store.save_diary(Diary(id=store.today(), claim="A long day.", body=body))

    assert body in _day_note(HookContext(event=HookEvent.STOP, event_data={}))


def test_the_note_names_the_point_the_day_is_compacted_from(store_dir):
    """The reviewer fits the page to a number, so it has to be the right one.

    Told to fit "under 8,000 characters", a rewrite landed at 7,980 and freed
    nothing: the append it was making room for was refused against the same wall,
    hour after hour. The note states the threshold the tool actually enforces, so
    the number the reviewer writes to and the number that refuses it agree.
    """
    at = compact_at(KIND_DIARY)
    store.save_diary(Diary(id=store.today(), claim="A day.", body="x" * (at - 600)))

    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))

    assert f"compacted from {at}" in note
    assert f"under {at} characters" in note


def test_a_day_with_no_entry_names_the_date_so_one_can_be_created(store_dir):
    """The reviewer is told `<today>` in the prompt and never what it is."""
    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))
    assert store.today() in note
    assert "no diary entry yet" in note


def test_the_note_is_offered_to_the_reviewer_but_not_to_the_log_hooks(store_dir):
    """The log hooks build no agent, so a note would be read for nothing."""
    assert build_memory_reviewer_hook_config().config.input_note is _day_note
    assert build_completed_log_hook_config().config.input_note is None
