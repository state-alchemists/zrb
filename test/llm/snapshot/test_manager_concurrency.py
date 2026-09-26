"""Tests for SnapshotManager — what happens when something else is already
using the store: another conversation's manager, another process, a slow
directory, or a caller that gave up waiting."""

import asyncio
import os
import tempfile
import threading
import time

import pytest

from zrb.llm.snapshot import RestoreOutcome, SnapshotManager
from zrb.llm.snapshot.manager import OPERATION_LOCK_NAME
from zrb.util.file_lock import hold_file_lock
from zrb.util.git.snapshot_store import SnapshotStore


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def snapshot_dir():
    # Git may finish writing repository metadata just as the fixture is torn
    # down under xdist; cleanup should not turn a passing test into an error.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield d


def _store_path(snapshot_dir):
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    return store


def _hold_the_store(store, held, release):
    """Stand in for another process's operation, holding the store's lock
    until *release* is set."""
    with hold_file_lock(os.path.join(store, OPERATION_LOCK_NAME)):
        held.set()
        release.wait(5)


@pytest.mark.asyncio
async def test_another_sessions_commit_in_the_same_store_is_refused(
    snapshot_dir, workdir
):
    target = os.path.join(workdir, "f.txt")
    with open(target, "w") as f:
        f.write("original")
    mine = SnapshotManager(snapshot_dir, "mine", workdir)
    theirs = SnapshotManager(snapshot_dir, "theirs", workdir)
    await mine.take_snapshot("mine")
    foreign = await theirs.take_snapshot("theirs")
    with open(target, "w") as f:
        f.write("edited")

    assert foreign is not None
    assert await mine.restore_snapshot(foreign) == RestoreOutcome(restored=False)
    with open(target) as f:
        assert f.read() == "edited"


@pytest.mark.asyncio
async def test_a_snapshot_waits_while_another_holds_the_store(snapshot_dir, workdir):
    """Another conversation's manager, or another process, restoring in the
    same directory: a snapshot must not catch it half-written."""
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    held, release = threading.Event(), threading.Event()
    thread = threading.Thread(
        target=_hold_the_store, args=(_store_path(snapshot_dir), held, release)
    )
    thread.start()
    held.wait(5)
    snapshot = asyncio.ensure_future(mgr.take_snapshot("second", message_count=1))

    await asyncio.sleep(0.3)
    assert not snapshot.done()
    release.set()
    assert await snapshot is not None
    thread.join()


@pytest.mark.asyncio
async def test_a_store_busy_past_the_wait_fails_that_snapshot_not_rewind(
    snapshot_dir, workdir, monkeypatch
):
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_LOCK_TIMEOUT", "0.2")
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    held, release = threading.Event(), threading.Event()
    thread = threading.Thread(
        target=_hold_the_store, args=(_store_path(snapshot_dir), held, release)
    )
    thread.start()
    held.wait(5)
    try:
        assert await mgr.take_snapshot("while stuck", message_count=1) is None
    finally:
        release.set()
        thread.join()

    assert mgr.unavailable_reason == ""
    assert await mgr.take_snapshot("after", message_count=1) is not None


@pytest.mark.asyncio
async def test_waiting_for_the_store_does_not_spend_the_operation_budget(
    snapshot_dir, workdir, monkeypatch
):
    """The budget starts once the store is held: a wait for a busy store is
    contention, not a directory too slow to snapshot, so it neither fails the
    operation on the budget nor turns rewind off."""
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_OPERATION_TIMEOUT", "5")
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    held, release = threading.Event(), threading.Event()
    thread = threading.Thread(
        target=_hold_the_store, args=(_store_path(snapshot_dir), held, release)
    )
    thread.start()
    held.wait(5)
    threading.Timer(3, release.set).start()
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_OPERATION_TIMEOUT", "2")
    try:
        sha = await mgr.take_snapshot("after a wait", message_count=1)
    finally:
        release.set()
        thread.join()

    assert sha is not None
    assert mgr.unavailable_reason == ""


@pytest.mark.asyncio
async def test_an_operation_past_its_budget_turns_rewind_off(
    snapshot_dir, workdir, monkeypatch
):
    """A directory too slow to hash within the budget fails every turn the
    same way a single command running past its own cap already did — rather
    than holding up each of them in turn."""
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    real_snapshot = SnapshotStore.snapshot

    def slow_snapshot(self, deadline=None):
        time.sleep(0.2)
        return real_snapshot(self, deadline)

    monkeypatch.setattr(SnapshotStore, "snapshot", slow_snapshot)
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_OPERATION_TIMEOUT", "0.05")

    assert await mgr.take_snapshot("too slow", message_count=1) is None
    assert "too large to snapshot in time" in mgr.unavailable_reason


@pytest.mark.asyncio
async def test_cancelling_a_snapshot_waiting_for_the_store_gives_up_at_once(
    snapshot_dir, workdir
):
    """The wait is not a git command, so nothing else would tell the worker
    its caller was gone; it would sit there for the store's whole timeout."""
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    held, release = threading.Event(), threading.Event()
    thread = threading.Thread(
        target=_hold_the_store, args=(_store_path(snapshot_dir), held, release)
    )
    thread.start()
    held.wait(5)
    snapshot = asyncio.ensure_future(mgr.take_snapshot("waiting", message_count=1))
    await asyncio.sleep(0.2)
    started = time.monotonic()
    try:
        snapshot.cancel()
        with pytest.raises(asyncio.CancelledError):
            await snapshot
    finally:
        release.set()
        thread.join()

    assert time.monotonic() - started < 5
    assert await SnapshotManager(snapshot_dir, "s", workdir).take_snapshot(
        "after", message_count=1
    )


@pytest.mark.asyncio
async def test_listing_never_waits_for_the_store(snapshot_dir, workdir):
    """It runs on the UI's thread: another process restoring, or setting the
    store up, must not freeze the UI."""
    await SnapshotManager(snapshot_dir, "s", workdir).take_init_snapshot()
    fresh = SnapshotManager(snapshot_dir, "s", workdir)  # a new process's
    held, release = threading.Event(), threading.Event()
    thread = threading.Thread(
        target=_hold_the_store, args=(_store_path(snapshot_dir), held, release)
    )
    thread.start()
    held.wait(5)
    try:
        started = time.monotonic()
        listed = fresh.list_snapshots()
        elapsed = time.monotonic() - started
    finally:
        release.set()
        thread.join()

    assert [snapshot.label for snapshot in listed] == ["init"]
    assert elapsed < 2
