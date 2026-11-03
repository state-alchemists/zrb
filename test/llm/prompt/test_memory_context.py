"""The injected block and its per-turn delta."""

import pytest

from zrb.config.config import CFG
from zrb.llm.memory import paths, store
from zrb.llm.memory.model import Fact
from zrb.llm.prompt import live_context
from zrb.llm.prompt.memory_context import render_memory_block, render_memory_delta
from zrb.llm.tool.memory import forget, remember


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_RECENT_MAX_CHARS", 1_600, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def test_a_compacted_context_carries_the_memory(store_dir, monkeypatch):
    """A compaction replaces the messages that carried the block, so it must carry it.

    Memory is the only store now, so the carried block is the memory and
    nothing else — there is no second index that could be the stale one.
    """
    remember("staging-ssh-port", "Staging SSH is port 2222.", pin=True)
    carried = live_context.render_carried_context()
    assert "Staging SSH is port 2222." in carried
    assert "<journal-index>" not in carried


def test_with_memory_off_the_carried_context_is_empty(store_dir, monkeypatch):
    """Off is the privacy switch: nothing is injected, and nothing stands in."""
    remember("staging-ssh-port", "Staging SSH is port 2222.", pin=True)
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", False, raising=False)
    assert live_context.render_carried_context() == ""


def test_an_empty_store_injects_nothing(store_dir):
    assert render_memory_block() is None


def test_the_block_carries_the_core_and_the_contract(store_dir):
    remember("staging-ssh-port", "Staging SSH is port 2222.", pin=True)
    block = render_memory_block()
    assert block is not None
    assert "<memory>" in block
    assert "Staging SSH is port 2222. [staging-ssh-port]" in block
    assert "data, not instructions" in block.lower() or "data." in block


def test_the_block_carries_todays_claim_and_the_log_tail(store_dir):
    day = store.today()
    remember(day, "Spent the day on memory.", kind="diary", body="Long day.")
    store.append_log("Replaced the journal with a memory store")
    block = render_memory_block()
    assert block is not None
    assert f"Today ({day}): Spent the day on memory." in block
    assert "Replaced the journal" in block


def test_the_recent_log_line_count_is_configurable(store_dir, monkeypatch):
    """The documented knob must be the one the block reads."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_RECENT_LOG_LINES", 1, raising=False)
    for minute in ("09:00", "10:00", "11:00"):
        store.append_log(f"event at {minute}", day=store.today())
    block = render_memory_block()
    assert block is not None
    assert "event at 11:00" in block
    assert "event at 09:00" not in block


def test_the_recent_block_is_cut_at_a_line_boundary(store_dir, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_RECENT_MAX_CHARS", 60, raising=False)
    remember(
        store.today(),
        "A day whose claim is too long for this small cap.",
        kind="diary",
        body="x",
    )
    store.append_log("An event line that will not fit either")
    block = render_memory_block()
    assert block is not None
    # Half a line is worse than none: the heading survives, the over-long line
    # does not.
    assert "too long for this small cap" not in block


def test_nothing_is_injected_when_memory_is_off(store_dir, monkeypatch):
    remember("x", "X is true.", pin=True)
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", False, raising=False)
    assert render_memory_block() is None
    assert render_memory_delta() is None


def test_the_delta_shows_a_claim_recorded_this_session(store_dir):
    remember("before", "Known before the session.", pin=True)
    assert render_memory_block() is not None
    remember("after", "Learned during the session.", pin=True)
    delta = render_memory_delta()
    assert delta is not None
    assert "Learned during the session." in delta
    assert "Known before the session." not in delta


def test_a_fact_cut_from_the_core_reaches_the_next_turn_as_a_delta(
    store_dir, monkeypatch
):
    """A migrated store larger than the cap must not lose its overflow.

    The block records only what the cap actually rendered as seen; the rest
    arrives as a delta rather than never arriving at all.
    """
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 70, raising=False)
    # Written directly: `remember` would refuse the third, which is the very
    # behaviour this test needs to look past — a migrated store arrives already
    # larger than the cap.
    for index in range(3):
        store.save_fact(
            Fact(
                id=f"fact-{index}",
                claim=f"Claim number {index}.",
                pin=True,
                updated=store.now(),
            )
        )
    store.write_core()
    block = render_memory_block()
    assert block is not None
    assert "fact-2" not in block
    delta = render_memory_delta()
    assert delta is not None
    assert "fact-2" in delta


def test_a_retired_day_is_tombstoned_once(store_dir):
    """The block showed the day; `Forget` must take it out of the model's hands."""
    day = store.today()
    remember(day, "Spent the day on memory.", kind="diary", body="x")
    assert render_memory_block() is not None
    forget(day, "wrong")
    delta = render_memory_delta()
    assert delta is not None
    assert f"Forget the day {day}" in delta
    assert render_memory_delta() is None


def test_a_diary_written_after_the_block_reaches_the_next_turn(store_dir):
    """A day is not a fact: the delta must carry it too, or the reviewer's work is
    invisible until a compaction."""
    remember("anchor", "An anchor claim.", pin=True)
    assert render_memory_block() is not None
    remember(store.today(), "Spent the day on memory.", kind="diary", body="x")
    delta = render_memory_delta()
    assert delta is not None
    assert "Spent the day on memory." in delta
    assert render_memory_delta() is None


def test_a_fact_recorded_after_an_empty_first_turn_is_shown(store_dir):
    """An empty store is still a first turn: it must leave a baseline.

    Without one, a fact remembered during the first turn of a new conversation
    had nothing to be "new" against, and the next turn showed nothing — the
    session recorded a fact and then answered as though it had not.
    """
    assert render_memory_block() is None
    remember("first-fact", "Learned on the first turn of an empty store.", pin=True)
    delta = render_memory_delta()
    assert delta is not None
    assert "Learned on the first turn of an empty store." in delta


def test_a_fact_left_out_by_the_cap_is_shown_next_turn(store_dir):
    """The emitter is capped at three lines; the baseline must not outrun it.

    Advancing the baseline to everything active would mark the fourth fact as
    already shown, and it would never be injected at all.
    """
    remember("anchor", "An anchor claim.", pin=True)
    assert render_memory_block() is not None
    for index in range(4):
        remember(f"fact-{index}", f"Claim number {index}.")
    first = render_memory_delta()
    assert first is not None
    assert len([line for line in first.splitlines() if line.startswith("- ")]) == 3
    second = render_memory_delta()
    assert second is not None
    assert len([line for line in second.splitlines() if line.startswith("- ")]) == 1
    assert render_memory_delta() is None


def test_a_forgotten_fact_that_was_never_shown_is_not_tombstoned(store_dir):
    """An unpinned fact is not in the block, so there is nothing to correct."""
    remember("unpinned", "A claim the block never carried.")
    # The block itself is empty, but the first turn still records its baseline.
    assert render_memory_block() is None
    forget("unpinned", "stale")
    assert render_memory_delta() is None


def test_a_forgotten_fact_is_tombstoned_once(store_dir):
    """The model must stop relying on a claim the block showed and Forget retired.

    A delta that lists only additions leaves the old claim in the transcript with
    nothing correcting it, so the session answers from a belief it just dropped.
    """
    remember("x", "X is true.", pin=True)
    assert render_memory_block() is not None
    forget("x", "stale")
    delta = render_memory_delta()
    assert delta is not None
    assert "Forget this claim: X is true. [x]" in delta
    # The tombstone is said once; after that the baseline no longer holds the id.
    assert render_memory_delta() is None


def test_the_delta_is_empty_when_nothing_was_recorded(store_dir):
    remember("x", "X is true.", pin=True)
    assert render_memory_block() is not None
    assert render_memory_delta() is None


def test_a_turn_without_a_baseline_gets_the_block(store_dir):
    """No block was ever rendered, so there is no session start to diff against —
    and a turn that has no baseline is a first turn, not an empty delta.

    Answering with nothing is what an upgrade looked like: a conversation resumed
    after the restart carried no memory, and the notes were not even read.
    """
    remember("x", "X is true.", pin=True)
    delta = render_memory_delta()
    assert delta is not None
    assert "<memory>" in delta
    assert "X is true." in delta


def test_a_resumed_conversation_reads_the_notes_on_first_use(tmp_path, monkeypatch):
    """The delta path converts too, because a resumed conversation is a first use.

    Conversion used to be reached only from the block, and a resumed conversation
    takes the delta path — so an upgrade could leave the notes unread for as long
    as that conversation kept being resumed.
    """
    notes = tmp_path / "llm-notes"
    category = notes / "user"
    category.mkdir(parents=True)
    (category / "identity.md").write_text(
        "---\nslug: identity\nupdated: 2026-10-28T12:00:36\npinned: true\n---\n\n"
        "# Identity\n\n**Finding:** Go is the user.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(CFG, "LLM_NOTES_DIR", str(notes), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(notes / "memory-v1"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    assert not paths.is_converted()

    delta = render_memory_delta()

    assert paths.is_converted()
    assert delta is not None
    assert store.load_facts(include_retired=True)
