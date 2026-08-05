from zrb.llm.tool.file_freshness import (
    is_file_fresh,
    is_file_tracked,
    mark_file_fresh,
    mark_file_stale,
    reset_file_freshness,
)


def setup_function():
    reset_file_freshness()


def teardown_function():
    reset_file_freshness()


def test_an_unseen_path_is_neither_tracked_nor_fresh():
    assert not is_file_tracked("/tmp/never-touched.py")
    assert not is_file_fresh("/tmp/never-touched.py")


def test_marking_fresh_makes_a_path_tracked_and_current():
    mark_file_fresh("/tmp/seen.py")

    assert is_file_tracked("/tmp/seen.py")
    assert is_file_fresh("/tmp/seen.py")


def test_marking_stale_keeps_it_tracked_but_not_current():
    """The distinction the denial message depends on: seen-but-changed vs never seen."""
    mark_file_fresh("/tmp/seen.py")
    mark_file_stale("/tmp/seen.py")

    assert is_file_tracked("/tmp/seen.py")
    assert not is_file_fresh("/tmp/seen.py")


def test_paths_are_compared_after_normalization():
    """A relative and an absolute reference to one file are one file."""
    import os

    mark_file_fresh(os.path.abspath("relative.py"))

    assert is_file_fresh("relative.py")


def test_reset_drops_everything():
    mark_file_fresh("/tmp/a.py")
    mark_file_stale("/tmp/b.py")

    reset_file_freshness()

    assert not is_file_tracked("/tmp/a.py")
    assert not is_file_tracked("/tmp/b.py")


def test_state_is_rebound_not_mutated():
    """A copied context must not see writes made after the copy.

    The dict is replaced on every transition precisely so a ContextVar copy
    cannot leak state back into its parent.
    """
    from zrb.llm.tool.file_freshness import file_freshness

    mark_file_fresh("/tmp/a.py")
    snapshot = file_freshness.get()
    mark_file_fresh("/tmp/b.py")

    assert "/tmp/b.py" not in snapshot
