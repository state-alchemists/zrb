"""What the core cap refuses, and what it must measure to refuse it.

The cap is the one place a write is turned away, so these tests pin the number
the refusal is decided on: the text the block will actually carry, not the file's
day-free rendering of it.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.memory import remember
from zrb.llm.contracts.memory import paths, store
from zrb.llm.contracts.memory.model import Fact
from zrb.llm.contracts.memory.render import render_core


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    return tmp_path / "memory"


def test_a_pin_that_does_not_fit_is_refused_and_nothing_is_written(
    store_dir, monkeypatch
):
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 90, raising=False)
    remember("first", "First claim takes most of the room.", pin=True)
    message = remember("second", "A second claim that will not fit.", pin=True)
    assert "Nothing was written" in message
    assert "current core" in message
    assert store.load_fact("second") is None
    assert "A second claim" not in store.read_document(paths.core_path())


def test_the_refusal_names_the_core_as_it_is_not_as_it_would_be(store_dir, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 90, raising=False)
    remember("first", "First claim takes most of the room.", pin=True)
    message = remember("second", "A second claim that will not fit.", pin=True)
    assert "[first]" in message
    assert "[second]" not in message


def test_a_loop_always_costs_core_room(store_dir, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 60, raising=False)
    remember("owed", "I owe a staging cert rotation.", kind="loop")
    message = remember("owed-2", "I owe a second thing as well.", kind="loop")
    assert "Nothing was written" in message


def test_the_cap_is_measured_on_the_block_which_dates_a_dormant_loop(
    store_dir, monkeypatch
):
    """A write measured on the day-free text passes the cap and is then cut.

    The block dates a loop nobody has touched; the file does not. A cap checked
    against the file's rendering lets the write through and then drops a claim
    from the block on the next turn, which is the outcome the refusal exists to
    prevent.
    """
    dormant = Fact(
        id="asleep", claim="An old thread.", kind="loop", updated="2020-01-01T00:00:00"
    )
    store.save_fact(dormant)
    store.write_core()
    fresh = Fact(id="fresh", claim="A fresh claim.", pin=True)
    undated = len(render_core([dormant, fresh]))
    dated = len(render_core([dormant, fresh], store.today()))
    assert dated > undated
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", dated - 1, raising=False)
    message = remember("fresh", "A fresh claim.", pin=True)
    assert "Nothing was written" in message
    assert store.load_fact("fresh") is None
