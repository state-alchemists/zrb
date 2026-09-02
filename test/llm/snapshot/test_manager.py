"""Tests for SnapshotManager — the shadow-git snapshot system for LLM /rewind."""

import os
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from zrb.llm.snapshot import Snapshot, SnapshotManager
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


# ── list_snapshots ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_snapshots_empty_before_any_snapshot(manager):
    assert manager.list_snapshots() == []


@pytest.mark.asyncio
async def test_list_snapshots_returns_snapshots_newest_first(manager, workdir):
    with open(os.path.join(workdir, "a.txt"), "w") as f:
        f.write("a")
    await manager.take_snapshot("first")

    with open(os.path.join(workdir, "b.txt"), "w") as f:
        f.write("b")
    await manager.take_snapshot("second")

    snapshots = manager.list_snapshots()
    assert len(snapshots) == 2
    assert snapshots[0].label == "second"
    assert snapshots[1].label == "first"


@pytest.mark.asyncio
async def test_list_snapshots_returns_snapshot_namedtuples(manager, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("x")
    await manager.take_snapshot("test label")

    snapshots = manager.list_snapshots()
    assert len(snapshots) == 1
    s = snapshots[0]
    assert isinstance(s, Snapshot)
    assert s.label == "test label"
    assert s.sha and len(s.sha) == 40
    assert s.timestamp


# ── message_count embedding ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_stores_message_count(manager, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")
    await manager.take_snapshot("with count", message_count=7)

    snapshots = manager.list_snapshots()
    assert snapshots[0].message_count == 7


@pytest.mark.asyncio
async def test_snapshot_message_count_is_none_when_not_provided(manager, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")
    await manager.take_snapshot("no count")

    snapshots = manager.list_snapshots()
    assert snapshots[0].message_count is None


# ── take_snapshot return value ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_snapshot_returns_40_char_sha(manager, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("hello")
    sha = await manager.take_snapshot("label")
    assert sha is not None
    assert len(sha) == 40


@pytest.mark.asyncio
async def test_take_snapshot_no_new_commit_when_files_unchanged(manager, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("same")
    sha1 = await manager.take_snapshot("first")

    # Nothing changed — should reuse HEAD commit
    sha2 = await manager.take_snapshot("second — same files")
    assert sha1 == sha2
    assert len(manager.list_snapshots()) == 1


# ── restore_snapshot ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_snapshot_reverts_modified_file(manager, workdir):
    file_path = os.path.join(workdir, "f.txt")
    with open(file_path, "w") as f:
        f.write("original")
    sha = await manager.take_snapshot("before edit")

    with open(file_path, "w") as f:
        f.write("modified")

    ok = await manager.restore_snapshot(sha)
    assert ok is True
    with open(file_path) as f:
        assert f.read() == "original"


@pytest.mark.asyncio
async def test_restore_snapshot_removes_file_added_after_snapshot(manager, workdir):
    with open(os.path.join(workdir, "original.txt"), "w") as f:
        f.write("keep")
    sha = await manager.take_snapshot("before add")

    new_file = os.path.join(workdir, "extra.txt")
    with open(new_file, "w") as f:
        f.write("extra")

    ok = await manager.restore_snapshot(sha)
    assert ok is True
    assert not os.path.exists(new_file)


@pytest.mark.asyncio
async def test_restore_snapshot_restores_deleted_file(manager, workdir):
    file_path = os.path.join(workdir, "f.txt")
    with open(file_path, "w") as f:
        f.write("important")
    sha = await manager.take_snapshot("before delete")

    os.remove(file_path)

    ok = await manager.restore_snapshot(sha)
    assert ok is True
    assert os.path.exists(file_path)
    with open(file_path) as f:
        assert f.read() == "important"


@pytest.mark.asyncio
async def test_restore_snapshot_returns_false_for_invalid_sha(manager, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")
    await manager.take_snapshot("some snapshot")

    ok = await manager.restore_snapshot("deadbeef" * 5)
    assert ok is False


@pytest.mark.asyncio
async def test_restore_snapshot_returns_false_when_no_snapshots_exist(manager):
    ok = await manager.restore_snapshot("abc123")
    assert ok is False


# ── .git directory is never touched ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_git_directory_in_workdir_is_preserved_after_restore(manager, workdir):
    """Regression: empty dirs inside .git must not be deleted during sync."""
    git_dir = os.path.join(workdir, ".git")
    heads_dir = os.path.join(git_dir, "refs", "heads")
    pack_dir = os.path.join(git_dir, "objects", "pack")
    os.makedirs(heads_dir, exist_ok=True)
    os.makedirs(pack_dir, exist_ok=True)
    with open(os.path.join(git_dir, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")
    sha = await manager.take_snapshot("with git dir")

    ok = await manager.restore_snapshot(sha)
    assert ok is True
    assert os.path.isdir(git_dir)
    assert os.path.isfile(os.path.join(git_dir, "HEAD"))
    assert os.path.isdir(heads_dir)
    assert os.path.isdir(pack_dir)


@pytest.mark.asyncio
async def test_snapshot_does_not_include_workdir_git_contents(manager, workdir):
    """The workdir's .git must never be copied into the shadow repo."""
    git_dir = os.path.join(workdir, ".git")
    os.makedirs(git_dir, exist_ok=True)
    with open(os.path.join(git_dir, "secret"), "w") as f:
        f.write("internal git state")

    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("real file")
    await manager.take_snapshot("should exclude .git")

    # The snapshot exists (no error), workdir .git still intact
    assert len(manager.list_snapshots()) == 1
    assert os.path.exists(os.path.join(git_dir, "secret"))


# ── error handling (graceful degradation) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_take_snapshot_returns_none_when_nothing_to_commit(manager):
    """Empty workdir → git has no HEAD after add → returns None gracefully."""
    result = await manager.take_snapshot("empty workdir")
    assert result is None


@pytest.mark.asyncio
async def test_take_snapshot_returns_none_when_setup_fails(workdir):
    """If the snapshot dir cannot be created, take_snapshot returns None."""
    with tempfile.NamedTemporaryFile() as f:
        # shadow dir parent is a file — os.makedirs will raise NotADirectoryError
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


# ── nested directory handling ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_snapshot_with_files_in_subdirectories(manager, workdir):
    """Subdirectories are recreated on restore when they were deleted."""
    import shutil

    subdir = os.path.join(workdir, "subdir")
    os.makedirs(subdir, exist_ok=True)
    file_path = os.path.join(subdir, "nested.txt")
    with open(file_path, "w") as f:
        f.write("nested content")
    sha = await manager.take_snapshot("with subdir")

    shutil.rmtree(subdir)

    ok = await manager.restore_snapshot(sha)
    assert ok is True
    with open(file_path) as f:
        assert f.read() == "nested content"


@pytest.mark.asyncio
async def test_restore_removes_stale_subdirectory(manager, workdir):
    """Restore removes directories that were added after the snapshot."""
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("original")
    sha = await manager.take_snapshot("clean")

    stale_dir = os.path.join(workdir, "stale_dir")
    os.makedirs(stale_dir, exist_ok=True)
    with open(os.path.join(stale_dir, "stale.txt"), "w") as wf:
        wf.write("stale")

    ok = await manager.restore_snapshot(sha)
    assert ok is True
    assert not os.path.exists(stale_dir)


# ── take_init_snapshot ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_init_snapshot_creates_commit_for_nonempty_workdir(
    snapshot_dir, workdir
):
    """take_init_snapshot syncs workdir files and creates the init commit (lines 108-119)."""
    with open(os.path.join(workdir, "hello.txt"), "w") as f:
        f.write("hello")

    mgr = SnapshotManager(snapshot_dir, "init-session", workdir)
    sha = await mgr.take_init_snapshot()

    assert sha is not None
    assert len(sha) == 40

    snapshots = mgr.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].label == "init"
    assert snapshots[0].message_count == 0


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


# ── force-empty commit when message_count advances ────────────────────────────


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


# ── every git subprocess call must be bounded ──
#
# A prior incident: an unbounded network call froze the whole TUI on a stall.
# A local shadow-repo git command is far less likely to hang, but "far less
# likely" was exactly the assumption that let the network case through
# unbounded too — every subprocess.run in this module must carry a timeout,
# so a stall here is a bounded wait, never a silent, permanent freeze.


# Captured before any patching, so the wrapper below calls the *real*
# subprocess.run rather than recursing into its own patch — `patch(
# "zrb.llm.snapshot.manager.subprocess.run", ...)` replaces `run` on the
# actual `subprocess` module object (manager.py's `import subprocess` is that
# same module, not a copy), so a wrapper that calls `subprocess.run` by name
# after patching calls *itself*, infinitely, silently swallowed by the
# manager's own `except Exception` handlers as a `RecursionError` — the git
# commands then never actually run, and the test would pass for the wrong
# reason (a same-value recursive echo) without checking anything real. An
# earlier version of this test had exactly that bug.
_real_subprocess_run = subprocess.run


def _run_records_timeout(*args, **kwargs):
    """Delegate to the real (pre-patch) subprocess.run so git genuinely
    runs, while recording whether a timeout was passed."""
    _run_records_timeout.calls.append(kwargs.get("timeout"))
    return _real_subprocess_run(*args, **kwargs)


_run_records_timeout.calls = []


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
