"""SnapshotStore.restore: per path, by its state now — rewritten, recreated,
removed only when the snapshot would have held it, or left alone — and every
path it could not write reported."""

import os
import subprocess

import pytest

from zrb.util.git.snapshot_store import SnapshotStore


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


def _snap(store: SnapshotStore) -> str:
    return store.snapshot().tree


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
    (repo / ".gitignore").write_bytes(b"*.log\n")
    (repo / "debug.log").write_bytes(b"precious\n")
    store = SnapshotStore(str(tmp_path / "snaps.git"), str(repo))
    before = _snap(store)  # debug.log is ignored: not captured
    (repo / ".gitignore").write_bytes(b"")  # logs un-ignored since
    (repo / "made.py").write_bytes(b"m\n")

    store.restore(before)  # the `.gitignore` edit is rewound

    assert (repo / ".gitignore").read_bytes() == b"*.log\n"
    assert (repo / "debug.log").read_bytes() == b"precious\n"
    assert not (repo / "made.py").exists()  # created since: removed


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
