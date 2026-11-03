"""The injected block and its per-turn delta."""

import pytest

from zrb.config.config import CFG
from zrb.llm.memory import paths, store
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
    remember("2026-11-03", "Spent the day on memory.", kind="diary", body="Long day.")
    store.append_log("Replaced the journal with a memory store")
    block = render_memory_block()
    assert block is not None
    assert "Today (2026-11-03): Spent the day on memory." in block
    assert "Replaced the journal" in block


def test_the_recent_block_is_cut_at_a_line_boundary(store_dir, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_RECENT_MAX_CHARS", 60, raising=False)
    remember("2026-11-03", "A day whose claim is too long for this small cap.", kind="diary", body="x")
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


def test_the_delta_is_empty_without_a_first_turn(store_dir):
    remember("x", "X is true.", pin=True)
    # No block was ever rendered, so there is no session start to diff against.
    assert render_memory_delta() is None
