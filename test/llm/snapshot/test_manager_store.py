"""Tests for SnapshotManager — where the git snapshot store lives and how
projects, sessions and directories are kept apart inside it."""

import asyncio
import os
import subprocess
import tempfile
import threading

import pytest

from zrb.llm.snapshot import RestoreOutcome, SnapshotManager
from zrb.llm.snapshot import manager as snapshot_manager
from zrb.llm.snapshot.manager import OPERATION_LOCK_NAME
from zrb.util.file_lock import hold_file_lock
from zrb.util.git.snapshot_command import SnapshotError
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


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.asyncio
async def test_workdir_inside_repo_honours_parent_gitignore_and_stays_in_scope(
    snapshot_dir, tmp_path
):
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "outside.txt").write_text("outside before")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "f.txt").write_text("original")
    (sub / "run.log").write_text("log before")
    mgr = SnapshotManager(snapshot_dir, "sub-session", str(sub))
    sha = await mgr.take_snapshot("in subdir")

    (sub / "f.txt").write_text("modified")
    (sub / "run.log").write_text("log after")
    (tmp_path / "outside.txt").write_text("outside after")
    assert sha is not None
    assert await mgr.restore_snapshot(sha) == RestoreOutcome(restored=True)

    assert (sub / "f.txt").read_text() == "original"
    assert (sub / "run.log").read_text() == "log after"
    assert (tmp_path / "outside.txt").read_text() == "outside after"
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert status == ["?? .gitignore", "?? outside.txt", "?? sub/"]


@pytest.mark.asyncio
async def test_sessions_of_one_directory_keep_separate_histories(snapshot_dir, workdir):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")
    a = SnapshotManager(snapshot_dir, "session-a", workdir)
    b = SnapshotManager(snapshot_dir, "session-b", workdir)

    await a.take_snapshot("from a")
    await b.take_snapshot("from b")

    assert [s.label for s in a.list_snapshots()] == ["from a"]
    assert [s.label for s in b.list_snapshots()] == ["from b"]
    assert len(os.listdir(snapshot_dir)) == 1  # one store for the directory


@pytest.mark.asyncio
async def test_session_resumed_in_another_subdir_leaves_the_first_alone(
    snapshot_dir, tmp_path
):
    _git(tmp_path, "init", "-q")
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "f.txt").write_text(f"{name} original")
    in_a = SnapshotManager(snapshot_dir, "resumed", str(tmp_path / "a"))
    await in_a.take_snapshot("in a")
    in_b = SnapshotManager(snapshot_dir, "resumed", str(tmp_path / "b"))
    sha = await in_b.take_snapshot("in b")

    (tmp_path / "b" / "f.txt").write_text("b modified")
    assert sha is not None
    assert await in_b.restore_snapshot(sha) == RestoreOutcome(restored=True)

    assert (tmp_path / "a" / "f.txt").read_text() == "a original"
    assert (tmp_path / "b" / "f.txt").read_text() == "b original"
    assert [s.label for s in in_b.list_snapshots()] == ["in b"]


@pytest.mark.skipif(os.name == "nt", reason="':' and '?' are invalid in Windows paths")
@pytest.mark.asyncio
async def test_paths_that_sanitize_alike_get_separate_stores(snapshot_dir, tmp_path):
    managers = []
    for name in ("a:b", "a?b"):
        workdir = tmp_path / name
        workdir.mkdir()
        (workdir / "f.txt").write_text(name)
        manager = SnapshotManager(snapshot_dir, "same-session", str(workdir))
        await manager.take_snapshot(f"in {name}")
        managers.append(manager)

    assert len(os.listdir(snapshot_dir)) == 2
    assert [s.label for s in managers[0].list_snapshots()] == ["in a:b"]
    assert [s.label for s in managers[1].list_snapshots()] == ["in a?b"]


@pytest.mark.asyncio
async def test_session_names_that_sanitize_alike_keep_separate_histories(
    snapshot_dir, workdir
):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("data")
    a = SnapshotManager(snapshot_dir, "a b", workdir)
    b = SnapshotManager(snapshot_dir, "a_b", workdir)

    await a.take_snapshot("from a b")
    await b.take_snapshot("from a_b")

    assert [s.label for s in a.list_snapshots()] == ["from a b"]
    assert [s.label for s in b.list_snapshots()] == ["from a_b"]


async def _rewind_twice_and_restore_first(snapshot_dir: str, workdir: str) -> None:
    """Two snapshots, then restore the first; the store must survive it."""
    file_path = os.path.join(workdir, "f.txt")
    with open(file_path, "w") as f:
        f.write("v1")
    mgr = SnapshotManager(snapshot_dir, "inside-session", workdir)
    first = await mgr.take_snapshot("one", message_count=1)
    with open(file_path, "w") as f:
        f.write("v2")
    await mgr.take_snapshot("two", message_count=2)

    assert first is not None
    assert await mgr.restore_snapshot(first) == RestoreOutcome(restored=True)
    with open(file_path) as f:
        assert f.read() == "v1"
    assert [s.label for s in mgr.list_snapshots()] == ["one"]
    with open(file_path, "w") as f:
        f.write("v3")
    assert await mgr.take_snapshot("three", message_count=3) is not None
    assert [s.label for s in mgr.list_snapshots()] == ["three", "one"]


@pytest.mark.asyncio
async def test_snapshot_dir_inside_the_workdir_is_never_snapshotted(workdir):
    await _rewind_twice_and_restore_first(os.path.join(workdir, ".snaps"), workdir)


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="'*' is invalid in Windows paths")
async def test_snapshot_dir_inside_a_repository_workdir_is_never_snapshotted(
    tmp_path,
):
    _git(tmp_path, "init", "-q")
    sub = tmp_path / "sub"
    sub.mkdir()
    # Glob characters in the name: the exclusion must match it literally.
    await _rewind_twice_and_restore_first(str(sub / "st*re [x]"), str(sub))


@pytest.mark.asyncio
async def test_relative_snapshot_dir_resolves_against_the_process_cwd(
    tmp_path, monkeypatch
):
    _git(tmp_path, "init", "-q")
    sub = tmp_path / "sub"
    sub.mkdir()
    monkeypatch.chdir(sub)
    await _rewind_twice_and_restore_first("snaps", str(sub))
    assert (sub / "snaps").is_dir()
    assert not (tmp_path / "snaps").exists()


@pytest.mark.asyncio
async def test_a_subdirectory_session_never_touches_files_outside_it(
    snapshot_dir, tmp_path
):
    _git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("readme")
    for package in ("app", "lib"):
        (tmp_path / "packages" / package).mkdir(parents=True)
        (tmp_path / "packages" / package / "m.py").write_text(package)
    app = SnapshotManager(snapshot_dir, "s", str(tmp_path / "packages" / "app"))
    own = await app.take_snapshot("app", message_count=1)
    (tmp_path / "README.md").write_text("edited")
    (tmp_path / "packages" / "lib" / "m.py").write_text("edited")
    (tmp_path / "packages" / "app" / "m.py").write_text("changed")

    assert own
    assert await app.restore_snapshot(own) == RestoreOutcome(restored=True)
    assert (tmp_path / "packages" / "app" / "m.py").read_text() == "app"
    assert (tmp_path / "packages" / "lib" / "m.py").read_text() == "edited"
    assert (tmp_path / "README.md").read_text() == "edited"


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
async def test_switching_conversation_switches_rewind_history(snapshot_dir, workdir):
    manager = SnapshotManager(snapshot_dir, "first", workdir)
    await manager.take_snapshot("in first", message_count=1)

    manager.session_name = "loaded"  # `/load loaded`
    await manager.take_snapshot("in loaded", message_count=7)

    assert [s.label for s in manager.list_snapshots()] == ["in loaded"]
    manager.session_name = "first"
    assert [s.label for s in manager.list_snapshots()] == ["in first"]


@pytest.mark.asyncio
async def test_a_saved_copy_keeps_the_conversations_rewind_history(
    snapshot_dir, workdir
):
    manager = SnapshotManager(snapshot_dir, "stale", workdir)
    await manager.take_snapshot("old", message_count=9)
    manager.session_name = "draft"
    await manager.take_snapshot("turn", message_count=2)

    manager.copy_history("draft", "final")  # `/save final`
    manager.copy_history("empty", "stale")  # `/save stale` from a fresh chat
    await manager.take_snapshot("applies both", message_count=2)

    manager.session_name = "final"
    assert [s.label for s in manager.list_snapshots()] == ["turn"]
    manager.session_name = "stale"
    assert manager.list_snapshots() == []  # its old counts matched no chat history


@pytest.mark.asyncio
async def test_a_snapshot_right_after_a_save_builds_on_the_copied_history(
    snapshot_dir, workdir
):
    """The next turn's snapshot can run before anything else once `/save`
    returns: the copy must still land first, not overwrite it."""
    manager = SnapshotManager(snapshot_dir, "draft", workdir)
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("one")
    await manager.take_snapshot("before save", message_count=1)

    manager.copy_history("draft", "final")  # `/save final`, then at once:
    manager.session_name = "final"
    assert [s.label for s in manager.list_snapshots()] == ["before save"]
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("two")
    await manager.take_snapshot("first turn after save", message_count=2)

    assert [s.label for s in manager.list_snapshots()] == [
        "first turn after save",
        "before save",
    ]


@pytest.mark.asyncio
async def test_a_copy_of_a_copy_takes_the_original_history(snapshot_dir, workdir):
    manager = SnapshotManager(snapshot_dir, "a", workdir)
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write("x")
    await manager.take_snapshot("in a", message_count=1)

    manager.copy_history("a", "b")  # `/save b`
    manager.copy_history("b", "c")  # `/save c`, before anything applied the first
    manager.session_name = "a"
    await manager.take_snapshot("a moves on", message_count=2)

    manager.session_name = "c"
    assert [s.label for s in manager.list_snapshots()] == ["in a"]


@pytest.mark.asyncio
async def test_a_restore_that_cannot_move_the_history_back_still_counts(
    snapshot_dir, workdir, monkeypatch
):
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    path = os.path.join(workdir, "f.txt")
    with open(path, "w") as f:
        f.write("then")
    sha = await mgr.take_snapshot("first")
    with open(path, "w") as f:
        f.write("now")
    await mgr.take_snapshot("second")
    real_git = SnapshotStore.git

    def refuse_update_ref(self, args, *rest, **kwargs):
        if args[0] == "update-ref":
            raise SnapshotError("cannot lock ref")
        return real_git(self, args, *rest, **kwargs)

    monkeypatch.setattr(SnapshotStore, "git", refuse_update_ref)

    assert await mgr.restore_snapshot(sha) == RestoreOutcome(restored=True)
    with open(path) as f:
        assert f.read() == "then"


@pytest.mark.asyncio
async def test_a_snapshot_waits_while_another_holds_the_store(snapshot_dir, workdir):
    """Another conversation's manager, or another process, restoring in the
    same directory: a snapshot must not catch it half-written."""
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    held, release = threading.Event(), threading.Event()

    def other_operation():
        with hold_file_lock(os.path.join(store, OPERATION_LOCK_NAME)):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=other_operation)
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
    monkeypatch.setattr(snapshot_manager, "STORE_LOCK_TIMEOUT_SECONDS", 0.2)
    mgr = SnapshotManager(snapshot_dir, "s", workdir)
    await mgr.take_init_snapshot()
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    held, release = threading.Event(), threading.Event()

    def stuck_operation():  # another process, stuck mid-restore
        with hold_file_lock(os.path.join(store, OPERATION_LOCK_NAME)):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=stuck_operation)
    thread.start()
    held.wait(5)
    try:
        assert await mgr.take_snapshot("while stuck", message_count=1) is None
    finally:
        release.set()
        thread.join()

    assert mgr.unavailable_reason == ""
    assert await mgr.take_snapshot("after", message_count=1) is not None
