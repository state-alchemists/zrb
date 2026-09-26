"""SnapshotStore.restore: per path, by its state now — rewritten, recreated,
removed only when the snapshot would have held it, or left alone — and every
path it could not write reported."""

import os
import shutil
import stat
import subprocess

import pytest

from zrb.util.git.snapshot_command import SnapshotTimeoutError
from zrb.util.git.snapshot_store import Snapshot, SnapshotStore


def _git(repo, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _nested(path, files: dict[str, str]):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    for name, content in files.items():
        (path / name).write_bytes(content.encode())
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


def _snap(store: SnapshotStore) -> Snapshot:
    return store.snapshot()


@pytest.fixture(autouse=True)
def _no_enclosing_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


needs_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)


def test_a_restore_rewrites_recreates_and_removes_inside_nested_repositories(
    repo, tmp_path
):
    lib = _nested(repo / "lib", {"v.py": "v\n", "keep.py": "k\n"})
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (lib / "v.py").write_text("changed\n")
    (lib / "keep.py").unlink()
    (lib / "new.py").write_text("new\n")
    (repo / "tracked.txt").write_text("changed\n")

    store.restore(before)

    assert (lib / "v.py").read_text() == "v\n"
    assert (lib / "keep.py").read_text() == "k\n"
    assert not (lib / "new.py").exists()
    assert (repo / "tracked.txt").read_text() == "a\n"
    assert _git(lib, "status", "--porcelain").stdout == ""


def test_a_restore_leaves_a_path_ignored_since_alone(repo, tmp_path):
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    (repo / "config.local").write_text("v1\n")
    before = _snap(store)
    (repo / ".gitignore").write_text("ignored.txt\nconfig.local\n")
    (repo / "config.local").write_text("v2\n")

    store.restore(before)

    assert (repo / "config.local").read_text() == "v2\n"


def test_a_restore_keeps_a_tracked_file_matching_an_ignore_pattern(repo, tmp_path):
    (repo / ".gitignore").write_bytes(b".env*\n")
    (repo / ".env.example").write_bytes(b"KEY=\n")
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-qm", "example")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (repo / ".env.example").write_bytes(b"KEY=changed\n")

    store.restore(before)

    assert (repo / ".env.example").read_bytes() == b"KEY=\n"


def test_a_restore_keeps_a_file_its_snapshot_ignored_then(repo, tmp_path):
    (repo / ".gitignore").write_bytes(b"*.log\nbuild/\n")
    (repo / "debug.log").write_bytes(b"precious\n")
    (repo / "build").mkdir()
    (repo / "build" / "out.bin").write_bytes(b"built\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)  # both ignored: not captured
    (repo / ".gitignore").write_bytes(b"")  # un-ignored since
    (repo / "made.py").write_bytes(b"m\n")

    store.restore(before)  # the `.gitignore` edit is rewound

    assert (repo / ".gitignore").read_bytes() == b"*.log\nbuild/\n"
    assert (repo / "debug.log").read_bytes() == b"precious\n"
    assert (repo / "build" / "out.bin").read_bytes() == b"built\n"
    assert not (repo / "made.py").exists()  # created since: removed


def test_a_restore_keeps_a_file_excluded_then_by_rules_no_snapshot_holds(
    repo, tmp_path
):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_bytes(b"secret.txt\n")
    (repo / "secret.txt").write_bytes(b"existed then\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    exclude.write_bytes(b"")  # `info/exclude` is in no snapshot's tree

    store.restore(before)

    assert (repo / "secret.txt").read_bytes() == b"existed then\n"


def test_a_restore_removes_what_was_made_since_in_a_repository_empty_then(
    repo, tmp_path
):
    lib = repo / "lib"
    lib.mkdir()
    _git(lib, "init", "-q")  # a repository, holding no file yet
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (lib / "made.py").write_bytes(b"m\n")

    store.restore(before)

    assert not (lib / "made.py").exists()


def test_a_restore_removes_what_was_made_since_in_a_repository_its_parent_ignores(
    repo, tmp_path
):
    (repo / ".gitignore").write_bytes(b"worktrees/\n")
    feature = _nested(repo / "worktrees" / "feature", {"f.py": "f\n"})
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)  # `worktrees/` left out, the repository in it listed
    (feature / "made.py").write_bytes(b"m\n")

    store.restore(before)

    assert not (feature / "made.py").exists()
    assert (feature / "f.py").read_bytes() == b"f\n"


@needs_permissions
def test_a_restore_keeps_what_a_directory_it_could_not_read_then_holds(repo, tmp_path):
    (repo / "volume").mkdir()
    (repo / "volume" / "data").write_bytes(b"existed then\n")
    (repo / "volume").chmod(0)  # a root-owned container volume, say
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    try:
        before = _snap(store)
    finally:
        (repo / "volume").chmod(0o755)  # readable since

    store.restore(before)

    assert (repo / "volume" / "data").read_bytes() == b"existed then\n"


def test_a_restore_leaves_a_repository_made_since_as_it_is(repo, tmp_path):
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    clone = _nested(repo / "vendor" / "lib", {"v.py": "v\n"})  # cloned since
    (clone / "wip.py").write_bytes(b"uncommitted\n")
    (repo / "made.txt").write_bytes(b"m\n")

    store.restore(before)

    assert (clone / "v.py").exists() and (clone / "wip.py").exists()
    assert not (repo / "made.txt").exists()


@needs_permissions
def test_a_restore_leaves_a_file_it_cannot_read_now_alone(repo, tmp_path):
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    notes = repo / "tracked.txt"
    notes.write_bytes(b"newer\n")
    notes.chmod(0)  # its current content is in no snapshot
    try:
        left_behind = store.restore(before)
    finally:
        notes.chmod(0o600)

    assert notes.read_bytes() == b"newer\n"
    assert left_behind == []


@needs_permissions
def test_a_restore_reports_what_it_could_not_write_and_a_second_one_finishes(
    repo, tmp_path
):
    (repo / "locked").mkdir()
    (repo / "locked" / "f.txt").write_bytes(b"a\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (repo / "locked" / "f.txt").write_bytes(b"b\n")
    (repo / "tracked.txt").write_bytes(b"b\n")
    (repo / "locked").chmod(0o555)  # its file cannot be replaced
    try:
        left_behind = store.restore(before)
    finally:
        (repo / "locked").chmod(0o755)

    assert left_behind == ["locked/f.txt"]
    assert (repo / "tracked.txt").read_bytes() == b"a\n"  # the rest is back
    assert store.restore(before) == []
    assert (repo / "locked" / "f.txt").read_bytes() == b"a\n"


@needs_permissions
def test_a_restore_leaves_what_a_directory_it_cannot_read_holds_alone(repo, tmp_path):
    (repo / "private").mkdir()
    (repo / "private" / "key.txt").write_bytes(b"old\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (repo / "private" / "key.txt").write_bytes(b"newer\n")
    (repo / "private").chmod(0o300)  # can write into it, cannot list it
    try:
        left_behind = store.restore(before)
    finally:
        (repo / "private").chmod(0o755)

    assert (repo / "private" / "key.txt").read_bytes() == b"newer\n"
    assert left_behind == []


def _ignores_case(directory) -> bool:
    probe = directory / "CaseProbe"
    probe.write_bytes(b"")
    try:
        return (directory / "caseprobe").exists()
    finally:
        probe.unlink()


def test_a_restore_across_a_case_only_rename_keeps_the_file(repo, tmp_path):
    if not _ignores_case(repo):
        pytest.skip("this filesystem tells letter case apart")
    (repo / "Readme.md").write_bytes(b"old\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (repo / "Readme.md").rename(repo / "README.md")  # the same file
    (repo / "README.md").write_bytes(b"newer\n")

    store.restore(before)

    assert (repo / "Readme.md").read_bytes() == b"old\n"


def test_a_restore_stopped_partway_reports_every_path_it_meant_to_change(
    repo, tmp_path, monkeypatch
):
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (repo / "tracked.txt").write_bytes(b"b\n")
    (repo / "new.txt").write_bytes(b"new\n")
    real_run_git = store.run_git

    def time_out_while_writing(args, *rest, **kwargs):
        if args[:2] == ["read-tree", "-u"]:
            # Killed at its timeout: part of the tree was written, the rest not.
            (repo / "tracked.txt").write_bytes(b"a\n")
            raise SnapshotTimeoutError("git read-tree timed out")
        return real_run_git(args, *rest, **kwargs)

    monkeypatch.setattr(store, "run_git", time_out_while_writing)
    left_behind = store.restore(before)
    monkeypatch.undo()

    assert left_behind == ["new.txt", "tracked.txt"]
    assert store.restore(before) == []
    assert not (repo / "new.txt").exists()


def test_a_restore_keeps_what_an_uninitialized_submodules_directory_held(
    repo, tmp_path
):
    upstream = _nested(tmp_path / "upstream", {"s.py": "s\n"})
    _git(
        repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(upstream),
        "sm",
    )
    _git(repo, "commit", "-qm", "sm")
    shutil.rmtree(repo / "sm" / ".git", ignore_errors=True)
    (repo / "sm" / ".git").unlink(missing_ok=True)  # a gitlink, no checkout
    (repo / "sm" / "notes.txt").write_bytes(b"existed then\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    _git(repo, "rm", "-q", "--cached", "sm")  # its files are listed since

    store.restore(before)

    assert (repo / "sm" / "notes.txt").read_bytes() == b"existed then\n"


def _write(path, content: bytes = b"x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _make_x_a_file(repo):
    _write(repo / "x", b"file then\n")


def _make_x_a_directory(repo):
    _write(repo / "x" / "f", b"file then\n")


def _replace_x_with_a_directory_of_ignored_files(repo):
    (repo / "x").unlink()
    _write(repo / "x" / "keep.o", b"ignored, in no snapshot\n")


def _replace_x_with_ignored_and_new_files(repo):
    _replace_x_with_a_directory_of_ignored_files(repo)
    _write(repo / "x" / "new.c", b"created since\n")


@pytest.mark.parametrize(
    "then, now, precious",
    [
        (_make_x_a_file, _replace_x_with_a_directory_of_ignored_files, "x/keep.o"),
        (_make_x_a_file, _replace_x_with_ignored_and_new_files, "x/keep.o"),
    ],
)
def test_a_restore_never_writes_over_what_no_snapshot_holds(
    repo, tmp_path, then, now, precious
):
    """`read-tree -u --reset` removes an untracked file or directory in the
    way of what it writes; what stands there unlisted is left, and the path
    reported."""
    (repo / ".gitignore").write_bytes(b"*.o\n")
    then(repo)
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    now(repo)
    content = (repo / precious).read_bytes()

    left_behind = store.restore(before)

    assert (repo / precious).read_bytes() == content
    assert "x" in left_behind
    assert not (repo / "x" / "new.c").exists()  # listed, created since: removed


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
@pytest.mark.parametrize("then, blocked", [("x", "x"), ("x/f", "x/f")])
def test_a_restore_never_writes_over_a_fifo(repo, tmp_path, then, blocked):
    """A FIFO where the snapshot has a file, or needs a directory: git
    cannot store it, so it is unlisted, and writing would destroy it."""
    _write(repo / then, b"file then\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    shutil.rmtree(repo / "x") if (repo / "x").is_dir() else (repo / "x").unlink()
    os.mkfifo(repo / "x")

    assert store.restore(before) == [blocked]
    assert stat.S_ISFIFO(os.lstat(repo / "x").st_mode)


@pytest.mark.parametrize("then_is_directory", [True, False])
def test_a_restore_replaces_a_listed_file_or_directory_in_its_way(
    repo, tmp_path, then_is_directory
):
    if then_is_directory:
        _write(repo / "x" / "f", b"file then\n")
    else:
        _write(repo / "x", b"file then\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    shutil.rmtree(repo / "x") if then_is_directory else (repo / "x").unlink()
    if then_is_directory:
        _write(repo / "x", b"a file since\n")  # listed: the restore's own
    else:
        _write(repo / "x" / "g", b"a directory since\n")

    assert store.restore(before) == []
    if then_is_directory:
        assert (repo / "x" / "f").read_bytes() == b"file then\n"
    else:
        assert (repo / "x").read_bytes() == b"file then\n"


def test_a_file_the_restore_keeps_is_never_written_over(repo, tmp_path):
    """A repository made since where the snapshot has a file: its files are
    kept, the tree cannot hold both, and the snapshot's file stays behind."""
    _write(repo / "x", b"file then\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)
    (repo / "x").unlink()
    _nested(repo / "x", {"work.py": "uncommitted work\n"})

    assert store.restore(before) == ["x"]
    assert (repo / "x" / "work.py").read_bytes() == b"uncommitted work\n"


def test_a_file_too_large_to_snapshot_is_left_out_and_left_alone(
    repo, tmp_path, monkeypatch
):
    """Left out like an ignored file: not held, never written over by a
    restore, never removed by one, and not reported as left behind."""
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_FILE_MAX_MB", str(10 / 2**20))
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    (repo / "data.bin").write_bytes(b"x" * 100)
    (repo / "small.txt").write_text("then\n")
    before = _snap(store)
    (repo / "data.bin").write_bytes(b"y" * 200)
    (repo / "small.txt").write_text("now\n")

    left_behind = store.restore(before)

    assert "data.bin" in before.left_out
    assert (repo / "data.bin").read_bytes() == b"y" * 200
    assert (repo / "small.txt").read_text() == "then\n"
    assert left_behind == []


def test_a_file_that_grew_too_large_is_not_overwritten_with_its_old_bytes(
    repo, tmp_path, monkeypatch
):
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_FILE_MAX_MB", str(10 / 2**20))
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    (repo / "grows.log").write_text("small\n")
    before = _snap(store)
    (repo / "grows.log").write_bytes(b"z" * 100)

    left_behind = store.restore(before)

    assert (repo / "grows.log").read_bytes() == b"z" * 100
    assert left_behind == []
