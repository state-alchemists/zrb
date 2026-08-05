"""The freshness bookkeeping itself, at the level of one path.

Freshness is a claim about a file on disk, so every case here works against a
real one. Marking a path that does not exist records nothing current — there is
no content for the model to hold a view of.
"""

import asyncio

import pytest

from zrb.llm.tool.file_freshness import (
    is_file_fresh,
    is_file_tracked,
    mark_file_fresh,
    mark_file_stale,
    reset_file_freshness,
)


@pytest.fixture(autouse=True)
def _clean_state():
    reset_file_freshness()
    yield
    reset_file_freshness()


@pytest.fixture
def seen(tmp_path):
    path = tmp_path / "seen.py"
    path.write_text("x = 1\n")
    return str(path)


def test_an_unseen_path_is_neither_tracked_nor_fresh(tmp_path):
    never = str(tmp_path / "never-touched.py")

    assert not is_file_tracked(never)
    assert not is_file_fresh(never)


def test_marking_fresh_makes_a_path_tracked_and_current(seen):
    mark_file_fresh(seen)

    assert is_file_tracked(seen)
    assert is_file_fresh(seen)


def test_marking_stale_keeps_it_tracked_but_not_current(seen):
    """The distinction the denial message depends on: seen-but-changed vs never seen."""
    mark_file_fresh(seen)
    mark_file_stale(seen)

    assert is_file_tracked(seen)
    assert not is_file_fresh(seen)


def test_paths_are_compared_after_normalization(tmp_path, monkeypatch):
    """A relative and an absolute reference to one file are one file."""
    (tmp_path / "relative.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)

    mark_file_fresh(str(tmp_path / "relative.py"))

    assert is_file_fresh("relative.py")


def test_a_change_on_disk_makes_a_fresh_view_stale(seen):
    """The recorded view is checked against the file, not merely remembered.

    Anything that writes without going through these tools — `sed -i`, a
    formatter, `git checkout`, a build step, a sub-agent — used to leave the
    bit reading fresh, and the whole-file overwrite that followed discarded the
    change. Nothing reports the write here; the stat is what notices.
    """
    mark_file_fresh(seen)
    assert is_file_fresh(seen)

    with open(seen, "w") as f:
        f.write("x = 2  # changed behind our back\n")

    assert not is_file_fresh(seen)
    assert is_file_tracked(seen)


def test_a_vanished_file_is_not_fresh(seen, tmp_path):
    """A path that has gone missing is not one the model holds a current view of."""
    import os

    mark_file_fresh(seen)
    os.remove(seen)

    assert not is_file_fresh(seen)


def test_state_survives_a_thread_hop(seen):
    """The regression that made the whole guard inert.

    `read_file` is synchronous, so `create_safe_wrapper` dispatches it through
    `asyncio.to_thread`, which runs it in a *copied* context. As `ContextVar`s
    these tables therefore recorded nothing: `mark_file_fresh` ran, the write
    was discarded on the way out, and every whole-file `Write` to an existing
    file was refused with "you have not read it" however many times it had just
    been read. Plain module state is what makes the write visible to the caller.
    """

    async def hop():
        await asyncio.to_thread(mark_file_fresh, seen)
        return is_file_fresh(seen)

    assert asyncio.run(hop())
