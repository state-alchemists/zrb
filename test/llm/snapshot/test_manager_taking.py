"""Tests for SnapshotManager — the git snapshot store for LLM /rewind."""

import asyncio
import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from zrb.llm.snapshot import RestoreOutcome, SnapshotManager
from zrb.llm.snapshot.manager import SnapshotProgress


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


_real_subprocess_run = subprocess.run


def _run_records_timeout(*args, **kwargs):
    'Delegate to the real (pre-patch) subprocess.run so git genuinely'
    _run_records_timeout.calls.append(kwargs.get("timeout"))
    return _real_subprocess_run(*args, **kwargs)


_run_records_timeout.calls = []


@pytest.mark.asyncio
async def test_take_init_snapshot_returns_existing_head_when_already_committed(
    snapshot_dir, workdir
):
    'Calling take_init_snapshot twice returns the same SHA without a new commit (lines 111-112).'
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "init-idempotent", workdir)
    sha1 = await mgr.take_init_snapshot()
    sha2 = await mgr.take_init_snapshot()

    assert sha1 == sha2
    assert len(mgr.list_snapshots()) == 1


@pytest.mark.asyncio
async def test_take_init_snapshot_returns_none_when_setup_fails(workdir):
    'When snapshot_dir is a file, take_init_snapshot returns None gracefully (lines 120-122).'
    with tempfile.NamedTemporaryFile() as f:
        mgr = SnapshotManager(f.name, "fail-session", workdir)
        result = await mgr.take_init_snapshot()
    assert result is None


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_start_and_done(snapshot_dir, workdir):
    """The progress callback sees "start" before hashing and "done" once the
    init commit exists. This directory is not a repository, so the snapshot
    lists loose files — the notice says so."""
    for name in ("a.txt", "b.txt"):
        with open(os.path.join(workdir, name), "w") as f:
            f.write(name)

    mgr = SnapshotManager(snapshot_dir, "progress-session", workdir)
    events: list[SnapshotProgress] = []
    sha = await mgr.take_init_snapshot(on_progress=events.append)

    assert sha is not None
    assert [(e.stage, e.skipped) for e in events] == [
        ("start", 0),
        ("notice", 0),
        ("done", 0),
    ]
    assert "no git repository" in events[1].reason


@pytest.mark.asyncio
async def test_take_init_snapshot_says_nothing_extra_in_a_repository(
    snapshot_dir, workdir
):
    'In a repository the snapshot reaches as far as the user expects, so'
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "repo-session", workdir)
    events: list[SnapshotProgress] = []
    assert await mgr.take_init_snapshot(on_progress=events.append) is not None

    assert [e.stage for e in events] == ["start", "done"]


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_up_to_date_when_repo_has_commits(
    snapshot_dir, workdir
):
    'Resuming an existing session reports up-to-date instead of copying.'
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "no-progress-session", workdir)
    await mgr.take_init_snapshot()

    events: list[SnapshotProgress] = []
    await mgr.take_init_snapshot(on_progress=events.append)

    assert [e.stage for e in events] == ["up-to-date"]


@pytest.mark.asyncio
async def test_take_init_snapshot_swallows_progress_callback_errors(
    snapshot_dir, workdir
):
    'A broken progress callback must not fail the snapshot.'
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "bad-callback-session", workdir)

    def _boom(event):
        raise RuntimeError("callback bug")

    sha = await mgr.take_init_snapshot(on_progress=_boom)

    assert sha is not None
    assert len(mgr.list_snapshots()) == 1


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_error_when_commit_fails_after_start(
    snapshot_dir, workdir
):
    "A failure after 'start' reports a terminal error event with reason."
    real_run = subprocess.run

    def _fail_commit_run(cmd, *args, **kwargs):
        if "commit-tree" in cmd:
            raise RuntimeError("commit boom")
        return real_run(cmd, *args, **kwargs)

    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "error-session", workdir)
    events: list[SnapshotProgress] = []
    with patch("subprocess.run", side_effect=_fail_commit_run):
        sha = await mgr.take_init_snapshot(on_progress=events.append)

    assert sha is None
    assert [e.stage for e in events] == ["start", "error"]
    assert "commit boom" in events[-1].reason


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
@pytest.mark.asyncio
async def test_take_init_snapshot_skips_unreadable_files_and_reports_them(
    snapshot_dir, workdir
):
    'One unreadable file (root-owned volume mount, protected key, ...) must'
    with open(os.path.join(workdir, "normal.txt"), "w") as f:
        f.write("fine")
    secret = os.path.join(workdir, "secret.key")
    with open(secret, "w") as f:
        f.write("protected")
    os.chmod(secret, 0)

    mgr = SnapshotManager(snapshot_dir, "skip-session", workdir)
    events: list[SnapshotProgress] = []
    try:
        sha = await mgr.take_init_snapshot(on_progress=events.append)
    finally:
        os.chmod(secret, 0o600)

    assert sha is not None
    assert [(e.stage, e.skipped) for e in events] == [
        ("start", 0),
        ("notice", 0),
        ("done", 1),
    ]
    assert len(mgr.list_snapshots()) == 1


@pytest.mark.asyncio
async def test_nested_repository_without_commits_does_not_break_snapshot(
    snapshot_dir, workdir
):
    nested = os.path.join(workdir, "vendor")
    os.makedirs(nested)
    subprocess.run(["git", "init", "-q"], cwd=nested, check=True)
    file_path = os.path.join(workdir, "f.txt")
    with open(file_path, "w") as f:
        f.write("original")

    mgr = SnapshotManager(snapshot_dir, "nested-session", workdir)
    sha = await mgr.take_snapshot("with nested repo")
    with open(file_path, "w") as f:
        f.write("modified")

    assert sha is not None
    assert await mgr.restore_snapshot(sha) == RestoreOutcome(restored=True)
    with open(file_path) as f:
        assert f.read() == "original"


@pytest.mark.asyncio
async def test_take_snapshot_force_empty_commit_when_message_count_advances(
    snapshot_dir, workdir
):
    "When files haven't changed but message_count increased, a new empty commit"
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("same content")

    mgr = SnapshotManager(snapshot_dir, "mc-session", workdir)
    sha1 = await mgr.take_snapshot("turn 1", message_count=1)
    assert sha1 is not None


    sha2 = await mgr.take_snapshot("turn 2", message_count=2)
    assert sha2 is not None


    assert sha1 != sha2

    snapshots = mgr.list_snapshots()
    assert len(snapshots) == 2
    assert snapshots[0].message_count == 2
    assert snapshots[1].message_count == 1


@pytest.mark.asyncio
async def test_every_git_subprocess_call_has_a_timeout(manager, workdir):
    _run_records_timeout.calls.clear()
    with patch(
        "zrb.util.git.snapshot_store.subprocess.run",
        side_effect=_run_records_timeout,
    ):
        with open(os.path.join(workdir, "a.txt"), "w") as f:
            f.write("a")
        sha = await manager.take_snapshot("first", message_count=1)
        snapshots = manager.list_snapshots()




    assert sha is not None
    assert len(snapshots) == 1
    assert _run_records_timeout.calls
    assert all(
        t is not None for t in _run_records_timeout.calls
    ), "every subprocess.run must pass timeout= -- found a call without one"


@pytest.mark.asyncio
async def test_a_cancelled_snapshot_never_moves_history_after_it_returns(
    manager, workdir
):
    'The git commands run in a worker thread cancelling cannot stop. The'
    import asyncio
    import threading

    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("v1")
    assert await manager.take_snapshot("kept", message_count=1) is not None
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("v2")

    in_commit = threading.Event()
    release = threading.Event()

    def slow_commit_tree(cmd, *args, **kwargs):
        if "commit-tree" in cmd:
            in_commit.set()
            release.wait(5)
        return _real_subprocess_run(cmd, *args, **kwargs)

    with patch(
        "zrb.util.git.snapshot_store.subprocess.run", side_effect=slow_commit_tree
    ):
        task = asyncio.create_task(manager.take_snapshot("late", message_count=2))
        await asyncio.to_thread(in_commit.wait, 5)
        task.cancel()
        threading.Timer(0.2, release.set).start()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert release.is_set()
    assert [s.label for s in manager.list_snapshots()] == ["kept"]


@pytest.mark.asyncio
async def test_a_snapshot_message_of_any_length_is_committed(manager, workdir):

    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("x")
    label = "x" * 200_000

    sha = await manager.take_snapshot(label, message_count=1)

    assert sha is not None
    assert manager.list_snapshots()[0].label == label


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label",
    [
        "zrb-snapshot: not-json",

        'first\nzrb-snapshot: {"unreadable": ["made.txt"], "left_out": [], '
        '"repositories": []}',
        "ends like a count [mc:5]",
    ],
)
async def test_no_label_passes_for_snapshot_metadata(manager, workdir, label):
    target = os.path.join(workdir, "f.txt")
    with open(target, "w") as f:
        f.write("original")
    sha = await manager.take_snapshot(label)
    with open(target, "w") as f:
        f.write("changed")
    made = os.path.join(workdir, "made.txt")
    with open(made, "w") as f:
        f.write("created since")

    outcome = await manager.restore_snapshot(sha)

    assert outcome.restored and not outcome.left_behind
    with open(target) as f:
        assert f.read() == "original"
    assert not os.path.exists(made)
    assert manager.list_snapshots()[0].message_count is None


@pytest.mark.asyncio
async def test_a_turn_snapshot_that_beats_the_init_snapshot_still_rewinds_the_turn(
    manager, workdir
):
    path = os.path.join(workdir, "f.txt")
    with open(path, "w") as f:
        f.write("before")

    async def first_turn():

        await manager.take_snapshot("first turn", message_count=0)
        with open(path, "w") as f:
            f.write("changed by the turn")

    events: list[SnapshotProgress] = []
    turn = asyncio.ensure_future(first_turn())
    init = asyncio.ensure_future(manager.take_init_snapshot(events.append))
    await asyncio.gather(turn, init)

    assert [event.stage for event in events] == ["up-to-date"]
    oldest = manager.list_snapshots()[-1]
    assert await manager.restore_snapshot(oldest.sha) == RestoreOutcome(restored=True)
    with open(path) as f:
        assert f.read() == "before"


def _git(cwd, *args) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.mark.asyncio
async def test_a_file_ignored_since_the_last_snapshot_gets_a_rewind_point(
    manager, workdir
):
    _git(workdir, "init", "-q")
    with open(os.path.join(workdir, ".gitignore"), "w") as f:
        f.write("*.log\n")
    first = await manager.take_snapshot("first", message_count=1)
    log = os.path.join(workdir, "debug.log")
    with open(log, "w") as f:
        f.write("existed at the second")

    second = await manager.take_snapshot("second", message_count=1)
    with open(os.path.join(workdir, ".gitignore"), "w") as f:
        f.write("")

    assert second != first
    assert await manager.restore_snapshot(second) == RestoreOutcome(restored=True)
    assert os.path.exists(log)


@pytest.mark.asyncio
async def test_a_commit_without_its_record_is_not_restored(
    manager, snapshot_dir, workdir
):
    made = os.path.join(workdir, "made.txt")
    await manager.take_snapshot("first", message_count=1)
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    (ref,) = _git(store, "for-each-ref", "--format=%(refname)", "refs/zrb").split()
    tree = _git(store, "rev-parse", f"{ref}^{{tree}}").strip()
    bare = _git(store, "commit-tree", tree, "-p", ref, "-m", "no record [mc:1]")
    _git(store, "update-ref", ref, bare.strip())
    with open(made, "w") as f:
        f.write("never seen by that commit")

    outcome = await manager.restore_snapshot(bare.strip())

    assert outcome == RestoreOutcome(restored=False)
    assert os.path.exists(made)
