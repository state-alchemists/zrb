"""SnapshotStore.restore: per path, by its state now — rewritten, recreated,
removed only when the snapshot would have held it, or left alone — and every
path it could not write reported."""

import os
import shutil
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
