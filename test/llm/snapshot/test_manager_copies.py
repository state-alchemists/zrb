"""Tests for SnapshotManager's `/save` copies: registered in memory when
`copy_history` is called, and applied before anything else of this manager
touches the store."""

import os
import tempfile
import threading

import pytest

from zrb.llm.snapshot import SnapshotManager
from zrb.llm.snapshot.manager import OPERATION_LOCK_NAME
from zrb.util.file_lock import hold_file_lock


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def snapshot_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield d


def _labels(manager) -> list[str]:
    return [s.label for s in manager.list_snapshots()]


def _write(workdir, text):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write(text)


@pytest.mark.asyncio
async def test_a_snapshot_right_after_save_in_the_same_task_builds_on_the_copy(
    snapshot_dir, workdir
):
    """The copy is registered when `copy_history` is called, so a turn the
    caller starts before its coroutine ever runs — without yielding in
    between — applies it first instead of being overwritten by it."""
    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)

    copy = mgr.copy_history("draft", "final")  # `/save final`, not yet run
    mgr.session_name = "final"
    _write(workdir, "turn")
    await mgr.take_snapshot("turn after save", message_count=2)
    await copy

    assert _labels(mgr) == ["turn after save", "in draft"]
    later = SnapshotManager(snapshot_dir, "final", workdir)
    await later.take_snapshot("next session", message_count=3)
    assert _labels(later) == ["next session", "turn after save", "in draft"]


@pytest.mark.asyncio
async def test_a_copy_the_store_was_busy_for_lands_at_the_next_operation(
    snapshot_dir, workdir, monkeypatch
):
    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    held, release = threading.Event(), threading.Event()

    def other_process():
        with hold_file_lock(os.path.join(store, OPERATION_LOCK_NAME)):
            held.set()
            release.wait(5)

    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_LOCK_TIMEOUT", "0.2")
    thread = threading.Thread(target=other_process)
    thread.start()
    held.wait(5)
    try:
        await mgr.copy_history("draft", "final")  # the store is busy
    finally:
        release.set()
        thread.join(5)
    mgr.session_name = "final"
    assert _labels(mgr) == ["in draft"]  # shown while it waits

    await mgr.take_snapshot("after", message_count=2)

    assert _labels(mgr) == ["after", "in draft"]


@pytest.mark.asyncio
async def test_a_copy_leaves_nothing_beside_the_store(snapshot_dir, workdir):
    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)
    before = sorted(os.listdir(snapshot_dir))

    await mgr.copy_history("draft", "final")

    assert sorted(os.listdir(snapshot_dir)) == before


@pytest.mark.asyncio
async def test_copies_land_in_the_order_they_were_registered(snapshot_dir, workdir):
    """`/save b` then `/save c` from b: c takes a's history even when its
    coroutine runs first."""
    mgr = SnapshotManager(snapshot_dir, "a", workdir)
    await mgr.take_snapshot("in a", message_count=1)

    to_b = mgr.copy_history("a", "b")
    to_c = mgr.copy_history("b", "c")
    await to_c
    await to_b

    for name in ("b", "c"):
        mgr.session_name = name
        assert _labels(mgr) == ["in a"]


@pytest.mark.asyncio
async def test_saving_over_a_name_a_pending_copy_depends_on_keeps_that_copy(
    snapshot_dir, workdir
):
    """`/save b`, `/save c` from b, then `/save b` again from x, before any
    lands: c must still get a's history, not b's replaced state."""
    first = SnapshotManager(snapshot_dir, "a", workdir)
    await first.take_snapshot("in a", message_count=1)
    _write(workdir, "x")
    await SnapshotManager(snapshot_dir, "x", workdir).take_snapshot("in x", 1)
    mgr = SnapshotManager(snapshot_dir, "a", workdir)

    copies = [
        mgr.copy_history("a", "b"),
        mgr.copy_history("b", "c"),
        mgr.copy_history("x", "b"),
    ]
    for copy in copies:
        await copy

    mgr.session_name = "b"
    assert _labels(mgr) == ["in x"]
    mgr.session_name = "c"
    assert _labels(mgr) == ["in a"]
