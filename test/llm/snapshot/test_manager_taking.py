"""Tests for SnapshotManager — the shadow-git snapshot system for LLM /rewind."""

import os
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from zrb.llm.snapshot import SnapshotManager
from zrb.llm.snapshot.manager import SnapshotProgress


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


@pytest.fixture
def manager(snapshot_dir, workdir):
    return SnapshotManager(snapshot_dir, "test-session", workdir)


_real_subprocess_run = subprocess.run


def _run_records_timeout(*args, **kwargs):
    """Delegate to the real (pre-patch) subprocess.run so git genuinely
    runs, while recording whether a timeout was passed."""
    _run_records_timeout.calls.append(kwargs.get("timeout"))
    return _real_subprocess_run(*args, **kwargs)


_run_records_timeout.calls = []


@pytest.mark.asyncio
async def test_take_init_snapshot_returns_existing_head_when_already_committed(
    snapshot_dir, workdir
):
    """Calling take_init_snapshot twice returns the same SHA without a new commit (lines 111-112)."""
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "init-idempotent", workdir)
    sha1 = await mgr.take_init_snapshot()
    sha2 = await mgr.take_init_snapshot()

    assert sha1 == sha2
    assert len(mgr.list_snapshots()) == 1


@pytest.mark.asyncio
async def test_take_init_snapshot_returns_none_when_setup_fails(workdir):
    """When snapshot_dir is a file, take_init_snapshot returns None gracefully (lines 120-122)."""
    with tempfile.NamedTemporaryFile() as f:
        mgr = SnapshotManager(f.name, "fail-session", workdir)
        result = await mgr.take_init_snapshot()
    assert result is None


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_start_and_done_with_copied_count(
    snapshot_dir, workdir
):
    """The progress callback sees "start" before the copy and the copied
    file count once the init commit exists."""
    for name in ("a.txt", "b.txt"):
        with open(os.path.join(workdir, name), "w") as f:
            f.write(name)

    mgr = SnapshotManager(snapshot_dir, "progress-session", workdir)
    events: list[SnapshotProgress] = []
    sha = await mgr.take_init_snapshot(on_progress=events.append)

    assert sha is not None
    assert [(e.stage, e.copied, e.skipped) for e in events] == [
        ("start", 0, 0),
        ("done", 2, 0),
    ]


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_up_to_date_when_repo_has_commits(
    snapshot_dir, workdir
):
    """Resuming an existing session reports up-to-date instead of copying."""
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
    """A broken progress callback must not fail the snapshot."""
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "bad-callback-session", workdir)

    def _boom(event):
        raise RuntimeError("callback bug")

    sha = await mgr.take_init_snapshot(on_progress=_boom)

    assert sha is not None
    assert len(mgr.list_snapshots()) == 1


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_done_with_zero_copies_when_tree_matches(
    snapshot_dir, workdir
):
    """A shadow tree that already matches the workdir (e.g. a prior run
    copied files but the commit never landed) still reports a terminal
    done event — with 0 copies, not a dangling start."""
    from zrb.util.string.conversion import to_safe_filename

    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")

    mgr = SnapshotManager(snapshot_dir, "zero-copy-session", workdir)
    await mgr.take_init_snapshot()
    # Roll HEAD back to nothing while keeping the copied tree in place. The
    # shadow-repo layout (<snapshot_dir>/<safe_session_name>) is documented
    # in the module docstring.
    shadow_dir = os.path.join(snapshot_dir, to_safe_filename("zero-copy-session"))
    subprocess.run(["git", "update-ref", "-d", "HEAD"], cwd=shadow_dir, check=True)

    events: list[SnapshotProgress] = []
    sha = await mgr.take_init_snapshot(on_progress=events.append)

    assert sha is not None
    assert [(e.stage, e.copied, e.skipped) for e in events] == [
        ("start", 0, 0),
        ("done", 0, 0),
    ]


@pytest.mark.asyncio
async def test_take_init_snapshot_reports_error_when_commit_fails_after_start(
    snapshot_dir, workdir
):
    """A failure after 'start' reports a terminal error event with reason."""
    real_run = subprocess.run

    def _fail_commit_run(cmd, *args, **kwargs):
        if "commit" in cmd:
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


@pytest.mark.asyncio
async def test_take_init_snapshot_skips_unreadable_files_and_reports_them(
    snapshot_dir, workdir
):
    """One unreadable file (root-owned volume mount, protected key, ...) must
    not abort the snapshot: it's skipped, counted, and the rest is committed."""
    real_copy2 = shutil.copy2

    def _deny_secret(src, dst, **kwargs):
        if os.path.basename(src) == "secret.key":
            raise PermissionError(13, "Permission denied", src)
        return real_copy2(src, dst, **kwargs)

    with open(os.path.join(workdir, "normal.txt"), "w") as f:
        f.write("fine")
    with open(os.path.join(workdir, "secret.key"), "w") as f:
        f.write("protected")

    mgr = SnapshotManager(snapshot_dir, "skip-session", workdir)
    events: list[SnapshotProgress] = []
    with patch("zrb.llm.snapshot.manager.shutil.copy2", side_effect=_deny_secret):
        sha = await mgr.take_init_snapshot(on_progress=events.append)

    assert sha is not None
    assert [(e.stage, e.copied, e.skipped) for e in events] == [
        ("start", 0, 0),
        ("done", 1, 1),
    ]

    snapshots = mgr.list_snapshots()
    assert len(snapshots) == 1  # snapshot still usable for /rewind


@pytest.mark.asyncio
async def test_take_snapshot_force_empty_commit_when_message_count_advances(
    snapshot_dir, workdir
):
    """When files haven't changed but message_count increased, a new empty commit
    is created so the correct mc is always stored at HEAD (lines 92-96)."""
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("same content")

    mgr = SnapshotManager(snapshot_dir, "mc-session", workdir)
    sha1 = await mgr.take_snapshot("turn 1", message_count=1)
    assert sha1 is not None

    # Same files, but message_count has advanced → must produce a NEW commit
    sha2 = await mgr.take_snapshot("turn 2", message_count=2)
    assert sha2 is not None

    # The two SHAs must differ because a force-empty commit was made
    assert sha1 != sha2

    snapshots = mgr.list_snapshots()
    assert len(snapshots) == 2
    assert snapshots[0].message_count == 2
    assert snapshots[1].message_count == 1


@pytest.mark.asyncio
async def test_every_git_subprocess_call_has_a_timeout(manager, workdir):
    _run_records_timeout.calls.clear()
    with patch(
        "zrb.llm.snapshot.manager.subprocess.run",
        side_effect=_run_records_timeout,
    ):
        with open(os.path.join(workdir, "a.txt"), "w") as f:
            f.write("a")
        sha = await manager.take_snapshot("first", message_count=1)
        snapshots = manager.list_snapshots()

    # Confirm git actually ran end-to-end (not swallowed as a recursion
    # error) -- a broken wrapper recursing into itself would still populate
    # `calls`, just without ever producing a real commit.
    assert sha is not None
    assert len(snapshots) == 1
    assert _run_records_timeout.calls  # sanity: at least one call recorded
    assert all(
        t is not None for t in _run_records_timeout.calls
    ), "every subprocess.run must pass timeout= -- found a call without one"
