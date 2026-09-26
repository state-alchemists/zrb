"""When SnapshotManager turns rewind off for the session, and how it says
why: a snapshot directory that is the working directory itself, a store that
cannot be set up, or more loose files than the listing's budget."""

import os
import subprocess
import sys
import tempfile
import time

import pytest

from zrb.llm.snapshot import SnapshotManager, SnapshotProgress


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def snapshot_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield d


@pytest.fixture
def manager(snapshot_dir, workdir):
    return SnapshotManager(snapshot_dir, "test-session", workdir)


@pytest.mark.asyncio
async def test_take_snapshot_returns_none_when_setup_fails(workdir):
    """If the snapshot dir cannot be created, take_snapshot returns None."""
    with tempfile.NamedTemporaryFile() as f:
        # snapshot dir is a file — os.makedirs will raise NotADirectoryError
        mgr = SnapshotManager(f.name, "test-session", workdir)
        with open(os.path.join(workdir, "x.txt"), "w") as wf:
            wf.write("x")
        result = await mgr.take_snapshot("will fail")
    assert result is None


def test_list_snapshots_returns_empty_when_setup_fails(workdir):
    """If initialization fails, list_snapshots returns [] rather than raising."""
    with tempfile.NamedTemporaryFile() as f:
        mgr = SnapshotManager(f.name, "test-session", workdir)
        result = mgr.list_snapshots()
    assert result == []


@pytest.mark.asyncio
async def test_a_directory_over_the_budget_turns_rewind_off_for_the_session(
    manager, workdir, monkeypatch
):

    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_LOOSE_MAX_FILES", "1")
    for name in ("a.txt", "b.txt"):
        with open(os.path.join(workdir, name), "w") as f:
            f.write("x")
    events = []

    assert await manager.take_init_snapshot(on_progress=events.append) is None
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_LOOSE_MAX_FILES", "100")

    assert events[-1].stage == "error"
    assert "more than 1 files outside any git repository" in events[-1].reason
    assert await manager.take_snapshot("later") is None


@pytest.mark.asyncio
async def test_a_store_that_cannot_be_set_up_turns_rewind_off_with_its_reason(
    workdir, tmp_path
):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the snapshot directory should be")
    manager = SnapshotManager(str(blocker), "s", workdir)
    events: list = []

    assert await manager.take_init_snapshot(on_progress=events.append) is None

    assert "is unusable" in manager.unavailable_reason
    assert events == [SnapshotProgress("error", reason=manager.unavailable_reason)]
    blocker.unlink()  # fixing it mid-session does not bring rewind back
    assert await manager.take_snapshot("later") is None
    assert manager.list_snapshots() == []
    assert not blocker.exists()


@pytest.mark.asyncio
async def test_a_snapshot_dir_equal_to_the_workdir_turns_rewind_off_with_a_reason(
    workdir,
):
    manager = SnapshotManager(workdir, "s", workdir)
    events: list = []

    assert await manager.take_init_snapshot(on_progress=events.append) is None
    assert await manager.take_snapshot("turn") is None

    assert "working directory itself" in manager.unavailable_reason
    assert events == [SnapshotProgress("error", reason=manager.unavailable_reason)]
    assert os.listdir(workdir) == []  # no store written into it


def _count_git_and_time_out(monkeypatch) -> list:
    """Every git command runs past its time limit; returns the call log."""
    import subprocess

    calls: list = []
    real_run = subprocess.run

    def run(argv, *args, **kwargs):
        calls.append(argv)
        if "update-index" in argv:
            raise subprocess.TimeoutExpired(argv, 30)
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    return calls


@pytest.mark.asyncio
async def test_a_directory_too_large_to_snapshot_in_time_turns_rewind_off(
    manager, workdir, monkeypatch
):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("x")
    calls = _count_git_and_time_out(monkeypatch)

    assert await manager.take_init_snapshot() is None
    assert "too large to snapshot in time" in manager.unavailable_reason
    tried = len(calls)
    assert await manager.take_snapshot("next turn") is None
    assert len(calls) == tried  # not held up again


_SET_UP_AND_SNAPSHOT = """
import asyncio, os, sys, time
from zrb.llm.snapshot import SnapshotManager
while not os.path.exists(sys.argv[4]):  # every process starts at once
    time.sleep(0.005)
manager = SnapshotManager(sys.argv[1], sys.argv[3], sys.argv[2])
sha = asyncio.run(manager.take_init_snapshot())
print(sha if sha else manager.unavailable_reason)
"""


def test_processes_setting_up_one_store_at_once_all_get_rewind(tmp_path):
    snapshot_dir, workdir = tmp_path / "snapshots", tmp_path / "work"
    go = tmp_path / "go"
    workdir.mkdir()
    (workdir / "f.txt").write_text("f\n")
    starts = [
        subprocess.Popen(
            [sys.executable, "-c", _SET_UP_AND_SNAPSHOT]
            + [str(snapshot_dir), str(workdir), f"conversation-{i}", str(go)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for i in range(16)
    ]
    time.sleep(1)  # every process imported and waiting
    go.touch()
    outputs = [process.communicate(timeout=60)[0].strip() for process in starts]

    assert all(len(output) == 40 for output in outputs), outputs


@pytest.mark.asyncio
async def test_without_git_rewind_is_off_with_its_reason(tmp_path, monkeypatch):
    from zrb.llm.snapshot import manager as snapshot_manager
    from zrb.llm.snapshot.manager import GIT_MISSING_REASON

    monkeypatch.setattr(snapshot_manager.shutil, "which", lambda name: None)
    mgr = SnapshotManager(str(tmp_path / "snapshots"), "s", str(tmp_path))

    assert mgr.unavailable_reason == GIT_MISSING_REASON
    assert await mgr.take_snapshot("turn") is None


@pytest.mark.asyncio
async def test_a_snapshot_cancelled_while_setting_the_store_up_leaves_rewind_on(
    tmp_path,
):
    """Cancelling says nothing about the store: the setup is tried again by
    the next operation, which succeeds."""
    import asyncio
    import threading

    from zrb.llm.snapshot.manager import OPERATION_LOCK_NAME
    from zrb.util.file_lock import hold_file_lock

    workdir, snapshots = str(tmp_path / "work"), str(tmp_path / "snapshots")
    os.makedirs(workdir)
    await SnapshotManager(snapshots, "other", workdir).take_snapshot("x")
    (store,) = [e.path for e in os.scandir(snapshots) if e.name.endswith(".git")]
    held, release = threading.Event(), threading.Event()

    def other_process():
        with hold_file_lock(os.path.join(store, OPERATION_LOCK_NAME)):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=other_process)
    thread.start()
    held.wait(5)
    mgr = SnapshotManager(snapshots, "s", workdir)
    try:
        task = asyncio.create_task(mgr.take_snapshot("turn"))
        await asyncio.sleep(0.3)  # waiting for the store's lock, mid-setup
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        thread.join(5)

    assert mgr.unavailable_reason == ""
    assert await mgr.take_snapshot("after", message_count=1) is not None
