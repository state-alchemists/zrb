"""First use: an unconverted notes directory is read into the store, once.

An upgrade that silently starts an empty memory looks exactly like a memory that
was lost, so the conversion runs when the store is first touched rather than from
a command the user has to know about. What these tests hold down is the *once*:
a marker, written after the pass, and an id that is never written twice.
"""

import os

import pytest

from zrb.config.config import CFG
from zrb.llm.memory import migrate, paths, store

NOTE = """---
slug: windows-ci-red-at-install-dependencies
updated: 2026-10-28T12:00:36
pinned: true
---

# Windows CI red at install dependencies

**Finding:** Compare the patch version before deleting the cache.
"""


@pytest.fixture
def notes_tree(tmp_path, monkeypatch):
    """A notes directory holding one note, with the store inside it as the default."""
    notes = tmp_path / "llm-notes"
    category = notes / "technical"
    category.mkdir(parents=True)
    (category / "windows-ci.md").write_text(NOTE, encoding="utf-8")
    monkeypatch.setattr(CFG, "LLM_NOTES_DIR", str(notes), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(notes / "memory-v1"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    return notes


def test_first_use_reads_the_notes_and_marks_the_directory(notes_tree):
    paths.prepare()
    fact = store.load_fact("windows-ci-red-at-install-dependencies")
    assert fact is not None
    assert fact.source == "migrated"
    assert fact.pin is True
    with open(os.path.join(str(notes_tree), ".version"), encoding="utf-8") as f:
        assert f.read().strip() == paths.NOTES_VERSION


def test_the_conversion_happens_once(notes_tree):
    """A note added after the marker is not read: the marker is what says we are done."""
    paths.prepare()
    (notes_tree / "technical" / "second.md").write_text(
        NOTE.replace("windows-ci", "second-ci"), encoding="utf-8"
    )
    paths.prepare()
    assert store.load_fact("second-ci-red-at-install-dependencies") is None


def test_a_marker_this_build_does_not_know_is_left_alone(notes_tree):
    """A newer zrb owns these notes; reading them with an older idea loses data."""
    (notes_tree / ".version").write_text("2\n", encoding="utf-8")
    paths.prepare()
    assert store.load_facts() == []
    with open(str(notes_tree / ".version"), encoding="utf-8") as f:
        assert f.read().strip() == "2"


def test_a_store_outside_the_notes_directory_does_not_convert(
    notes_tree, tmp_path, monkeypatch
):
    """Someone pointed the store elsewhere; converting their notes into it is a surprise."""
    monkeypatch.setattr(
        CFG, "LLM_MEMORY_DIR", str(tmp_path / "elsewhere"), raising=False
    )
    paths.prepare()
    assert store.load_facts() == []
    assert not os.path.exists(str(notes_tree / ".version"))


def test_an_interrupted_conversion_continues_without_duplicating(notes_tree):
    """The crash case: facts written, marker not. The next start finishes the job."""
    migrate.migrate()
    assert len(store.load_facts()) == 1
    assert not os.path.exists(str(notes_tree / ".version"))
    paths.prepare()
    assert len(store.load_facts()) == 1
    assert os.path.exists(str(notes_tree / ".version"))
