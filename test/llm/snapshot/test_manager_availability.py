"""When SnapshotManager turns rewind off for the session, and how it says
why: a snapshot directory that is the working directory itself, a store that
cannot be set up, or more loose files than the listing's budget."""

import os
import tempfile

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
    from zrb.util.git import snapshot_listing

    monkeypatch.setattr(snapshot_listing, "LOOSE_FILE_LIMIT", 1)
    for name in ("a.txt", "b.txt"):
        with open(os.path.join(workdir, name), "w") as f:
            f.write("x")
    events = []

    assert await manager.take_init_snapshot(on_progress=events.append) is None
    monkeypatch.setattr(snapshot_listing, "LOOSE_FILE_LIMIT", 100)

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
