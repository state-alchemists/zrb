"""Tests for SnapshotManager housekeeping — what keeps a store from growing
without end: dropping the rewind history of conversations past their
retention, and letting git pack and prune the store."""

import os
import subprocess
import tempfile
import time

import pytest

from zrb.llm.snapshot import SnapshotManager
from zrb.util.git.snapshot_store import SnapshotStore


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def snapshot_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield d


def _refs(snapshot_dir) -> list[str]:
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    listing = subprocess.run(
        ["git", "--git-dir", store, "for-each-ref", "--format=%(refname)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return listing.split()


@pytest.mark.asyncio
async def test_init_snapshot_commits_before_housekeeping(
    snapshot_dir, workdir, monkeypatch
):
    commands: list[tuple[str, ...]] = []
    real_git = SnapshotStore.git

    def record_git(self, args, *positional, **keyword):
        commands.append(tuple(args))
        return real_git(self, args, *positional, **keyword)

    monkeypatch.setattr(SnapshotStore, "git", record_git)

    sha = await SnapshotManager(snapshot_dir, "s", workdir).take_init_snapshot()

    assert sha is not None
    commit_index = next(
        i for i, args in enumerate(commands) if args[0] == "commit-tree"
    )
    gc_index = next(
        i for i, args in enumerate(commands) if args[-3:] == ("gc", "--auto", "--quiet")
    )
    assert commit_index < gc_index


@pytest.mark.asyncio
async def test_a_history_past_its_retention_is_dropped_at_the_next_session(
    snapshot_dir, workdir
):
    old = SnapshotManager(snapshot_dir, "old", workdir, retention_seconds=1)
    await old.take_init_snapshot()
    time.sleep(2.1)  # commit dates have one-second resolution

    new = SnapshotManager(snapshot_dir, "new", workdir, retention_seconds=1)
    await new.take_init_snapshot()

    old.session_name = "old"
    assert old.list_snapshots() == []
    assert len(new.list_snapshots()) == 1
    assert len(_refs(snapshot_dir)) == 1


@pytest.mark.asyncio
async def test_a_resumed_conversation_keeps_its_own_history_however_old(
    snapshot_dir, workdir
):
    first = SnapshotManager(snapshot_dir, "s", workdir, retention_seconds=1)
    await first.take_init_snapshot()
    time.sleep(2.1)

    resumed = SnapshotManager(snapshot_dir, "s", workdir, retention_seconds=1)
    await resumed.take_init_snapshot()

    assert len(resumed.list_snapshots()) == 1


@pytest.mark.asyncio
async def test_no_retention_keeps_every_history(snapshot_dir, workdir):
    old = SnapshotManager(snapshot_dir, "old", workdir)
    await old.take_init_snapshot()
    new = SnapshotManager(snapshot_dir, "new", workdir)
    await new.take_init_snapshot()

    assert len(_refs(snapshot_dir)) == 2
