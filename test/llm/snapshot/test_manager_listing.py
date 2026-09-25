"""Tests for SnapshotManager — the git snapshot store for LLM /rewind."""

import os
import subprocess
import tempfile

import pytest

from zrb.llm.snapshot import Snapshot, SnapshotManager


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
    """The workdir's .git must never be snapshotted."""
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


@pytest.mark.asyncio
async def test_snapshot_of_empty_workdir_is_restorable(manager, workdir):
    sha = await manager.take_snapshot("empty workdir")
    new_file = os.path.join(workdir, "later.txt")
    with open(new_file, "w") as f:
        f.write("later")

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    assert not os.path.exists(new_file)


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
async def test_restore_drops_later_snapshots_from_the_list(manager, workdir):
    file_path = os.path.join(workdir, "f.txt")
    with open(file_path, "w") as f:
        f.write("one")
    first = await manager.take_snapshot("first", message_count=1)
    with open(file_path, "w") as f:
        f.write("two")
    await manager.take_snapshot("second", message_count=2)

    assert first is not None
    assert await manager.restore_snapshot(first) is True
    assert [s.label for s in manager.list_snapshots()] == ["first"]


@pytest.mark.asyncio
async def test_gitignored_files_are_neither_snapshotted_nor_restored(manager, workdir):
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    with open(os.path.join(workdir, ".gitignore"), "w") as f:
        f.write("*.log\n")
    log = os.path.join(workdir, "run.log")
    with open(log, "w") as f:
        f.write("before")
    sha = await manager.take_snapshot("with ignored file")
    with open(log, "w") as f:
        f.write("after")

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    with open(log) as f:
        assert f.read() == "after"


@pytest.mark.asyncio
async def test_default_ignore_dirs_apply_outside_git(manager, workdir):
    cache = os.path.join(workdir, "node_modules", "pkg.js")
    os.makedirs(os.path.dirname(cache))
    sha = await manager.take_snapshot("before install")
    with open(cache, "w") as f:
        f.write("installed")

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    assert os.path.exists(cache)


@pytest.mark.asyncio
async def test_file_ignored_after_a_snapshot_is_left_alone(manager, workdir):
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    secret = os.path.join(workdir, "secrets.env")
    with open(secret, "w") as f:
        f.write("v1")
    first = await manager.take_snapshot("secret tracked", message_count=1)
    with open(os.path.join(workdir, ".gitignore"), "w") as f:
        f.write("secrets.env\n")
    with open(secret, "w") as f:
        f.write("v2")
    second = await manager.take_snapshot("secret ignored", message_count=2)
    with open(secret, "w") as f:
        f.write("v3")

    assert first and second
    assert await manager.restore_snapshot(second) is True
    with open(secret) as f:
        assert f.read() == "v3"  # not in the second snapshot, so not removed
    assert await manager.restore_snapshot(first) is True
    with open(secret) as f:
        assert f.read() == "v3"  # ignored now, so the old copy is not restored


@pytest.mark.asyncio
async def test_restore_is_byte_exact_whatever_gitattributes_say(
    manager, workdir, monkeypatch
):
    # A smudge filter configured the way git-lfs is, and an eol rule: either
    # would rewrite restored bytes if the project's attributes applied.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "filter.spy.smudge")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "echo SMUDGED")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "filter.spy.clean")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "echo CLEANED")
    with open(os.path.join(workdir, ".gitattributes"), "w") as f:
        f.write("*.bin filter=spy\n*.txt text eol=crlf\n")
    contents = {"data.bin": b"\x00raw\n", "lf.txt": b"one\ntwo\n"}
    for name, data in contents.items():
        with open(os.path.join(workdir, name), "wb") as f:
            f.write(data)
    sha = await manager.take_snapshot("attributes")
    for name in contents:
        os.remove(os.path.join(workdir, name))

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    for name, data in contents.items():
        with open(os.path.join(workdir, name), "rb") as f:
            assert f.read() == data


@pytest.mark.asyncio
async def test_a_gitignore_outside_any_repository_has_no_effect(manager, workdir):
    """As in git itself: only a repository reads its `.gitignore`."""
    with open(os.path.join(workdir, ".gitignore"), "w") as f:
        f.write("*.log\n")
    log = os.path.join(workdir, "run.log")
    with open(log, "w") as f:
        f.write("before")
    sha = await manager.take_snapshot("loose")
    with open(log, "w") as f:
        f.write("after")

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    with open(log) as f:
        assert f.read() == "before"


@pytest.mark.asyncio
async def test_rewind_restores_the_files_of_nested_repositories(manager, workdir):
    lib = os.path.join(workdir, "lib")
    os.makedirs(lib)
    subprocess.run(["git", "init", "-q"], cwd=lib, check=True)
    source = os.path.join(lib, "v.py")
    with open(source, "w") as f:
        f.write("before")
    sha = await manager.take_snapshot("nested")
    with open(source, "w") as f:
        f.write("after")

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    with open(source) as f:
        assert f.read() == "before"


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
@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
async def test_rewind_keeps_a_file_its_snapshot_could_not_read(manager, workdir):
    locked = os.path.join(workdir, "locked.txt")
    with open(locked, "w") as f:
        f.write("mine")
    os.chmod(locked, 0)
    try:
        sha = await manager.take_snapshot("while locked")
    finally:
        os.chmod(locked, 0o600)

    assert sha is not None
    assert await manager.restore_snapshot(sha) is True
    with open(locked) as f:
        assert f.read() == "mine"
