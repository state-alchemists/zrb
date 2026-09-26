"""SnapshotStore's lifecycle: owner-only stores, deleted with every object
they wrote whatever races them, and index locks that never outlive — or take
another process's with — an operation."""

import os
import re
import shutil
import subprocess

import pytest

from zrb.util.git.snapshot_command import SnapshotError
from zrb.util.git.snapshot_store import SnapshotStore


def _snap(store: SnapshotStore) -> str:
    return store.snapshot().tree


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_a_temporary_store_is_owner_only(repo):
    store = SnapshotStore.create_temporary(str(repo))
    try:
        assert os.stat(store.git_dir).st_mode & 0o077 == 0
    finally:
        store.delete()


def test_a_store_is_deleted_with_its_objects(repo):
    store = SnapshotStore.create_temporary(str(repo))

    _snap(store)
    store.delete()

    assert not os.path.exists(store.git_dir)


def test_a_store_with_read_only_objects_is_still_deleted(repo):
    store = SnapshotStore.create_temporary(str(repo))
    (repo / "untracked.txt").write_bytes(b"new\n")
    _snap(store)
    for root, _dirs, files in os.walk(store.git_dir):
        for name in files:
            os.chmod(os.path.join(root, name), 0o444)  # as git leaves objects

    store.delete()

    assert not os.path.exists(store.git_dir)


def test_deleting_a_store_twice_or_a_missing_one_never_raises(repo):
    store = SnapshotStore.create_temporary(str(repo))
    _snap(store)

    store.delete()
    store.delete()  # a cleanup racing an earlier one must not mask its error

    assert not os.path.exists(store.git_dir)


def test_a_store_removed_by_a_racing_cleanup_mid_delete_never_raises(repo, monkeypatch):
    store = SnapshotStore.create_temporary(str(repo))
    _snap(store)
    real_rmtree = shutil.rmtree

    def racing_rmtree(path, *args, **kwargs):
        # Another cleanup — `delete`'s own, with its read-only handler, which
        # Windows needs for git's object files — wins after `delete`'s check.
        real_rmtree(path, *args, **kwargs)
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", racing_rmtree)

    store.delete()

    assert not os.path.exists(store.git_dir)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_a_persistent_store_is_owner_only_whatever_the_umask(repo, tmp_path):
    old = os.umask(0o022)
    try:
        store = SnapshotStore(str(tmp_path / "snaps" / "project.git"), str(repo))
        _snap(store)
    finally:
        os.umask(old)

    assert os.stat(store.git_dir).st_mode & 0o077 == 0


def _rmtree_refused(*args, **kwargs):
    raise PermissionError("locked by another process")


@pytest.mark.parametrize(
    "rmtree", [lambda *args, **kwargs: None, _rmtree_refused], ids=["kept", "raised"]
)
def test_a_store_that_cannot_be_deleted_is_reported_with_its_path(
    repo, monkeypatch, caplog, rmtree
):
    store = SnapshotStore.create_temporary(str(repo))
    _snap(store)
    monkeypatch.setattr(shutil, "rmtree", rmtree)

    with caplog.at_level("WARNING", logger="zrb.util.git.snapshot_store"):
        store.delete()

    assert store.git_dir in caplog.text
    monkeypatch.undo()
    store.delete()
    assert not os.path.exists(store.git_dir)


def _update_index_killed_at_timeout(monkeypatch):
    """Make the next `git update-index` behave like one killed at its
    timeout: it took its index's lock, and dies without removing it."""
    real_run = subprocess.run

    def run(argv, *args, **kwargs):
        if "update-index" in argv:
            open(kwargs["env"]["GIT_INDEX_FILE"] + ".lock", "w").close()
            raise subprocess.TimeoutExpired(argv, 30)
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)


def test_a_command_killed_at_its_timeout_takes_no_other_lock_with_it(
    repo, store, monkeypatch
):
    _snap(store)
    lock = store.index + ".lock"
    open(lock, "w").close()  # another git process is writing the index
    before = sorted(os.listdir(store.git_dir))
    _update_index_killed_at_timeout(monkeypatch)

    with pytest.raises(SnapshotError, match="timed out"):
        store.snapshot()
    monkeypatch.undo()

    # Its own index and lock are gone; the other process's lock is not.
    assert sorted(os.listdir(store.git_dir)) == before
    assert os.path.exists(lock)
    os.remove(lock)
    assert _snap(store)


def test_a_lock_another_process_holds_on_the_index_is_left_alone(repo, store):
    _snap(store)
    lock = store.index + ".lock"
    open(lock, "w").close()  # another git process is writing the index

    (repo / "tracked.txt").write_text("b\n")
    assert _snap(store)
    assert os.path.exists(lock)


def test_a_lock_taken_while_a_command_runs_survives_its_timeout(
    repo, store, monkeypatch
):
    _snap(store)
    lock = store.index + ".lock"
    real_run = subprocess.run

    def run(argv, *args, **kwargs):
        if "update-index" in argv:
            open(lock, "w").close()  # another process takes the index meanwhile
            raise subprocess.TimeoutExpired(argv, 30)
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(SnapshotError, match="timed out"):
        store.snapshot()

    assert os.path.exists(lock)


@pytest.mark.parametrize("inside", [False, True])
def test_a_store_that_would_hold_its_own_work_tree_is_refused(tmp_path, inside):
    workdir = tmp_path / "project" if inside else tmp_path
    workdir.mkdir(exist_ok=True)

    with pytest.raises(ValueError, match="cannot hold its own work tree"):
        SnapshotStore(str(tmp_path), str(workdir))


def test_an_operation_index_removed_by_a_racing_cleanup_never_fails_it(
    repo, store, monkeypatch
):
    real_exists = os.path.exists

    def seen_before_another_cleanup_removed_it(path):
        # An operation's own index or its lock: there when looked for, gone
        # by the time it is removed.
        return bool(re.search(r"index\.[0-9a-f]{32}", str(path))) or real_exists(path)

    monkeypatch.setattr(os.path, "exists", seen_before_another_cleanup_removed_it)

    assert store.snapshot().tree


def test_a_cache_copy_that_fails_partway_leaves_no_operation_index(
    repo, store, monkeypatch
):
    store.snapshot()  # the named index exists from here

    def copy_part_then_fail(source, destination, *args, **kwargs):
        with open(destination, "wb") as f:
            f.write(b"DIRC")  # the disk filled up mid-copy
        raise OSError("No space left on device")

    monkeypatch.setattr(shutil, "copy2", copy_part_then_fail)
    with pytest.raises(OSError):
        store.snapshot()

    assert not [n for n in os.listdir(store.git_dir) if n.startswith("index.")]


def test_opening_a_store_leaves_its_attribute_rules_in_place(repo, tmp_path):
    """Rewritten only when they differ: another process may be hashing under
    them, and a file seen empty mid-rewrite would let the project's filters
    in."""
    git_dir = str(tmp_path / "snaps.git")
    SnapshotStore(git_dir, str(repo)).ensure()
    attributes = os.path.join(git_dir, "info", "attributes")
    inode = os.stat(attributes).st_ino
    os.utime(attributes, (1, 1))

    SnapshotStore(git_dir, str(repo)).ensure()

    assert os.stat(attributes).st_mtime == 1
    assert os.stat(attributes).st_ino == inode


def test_a_store_whose_attribute_rules_were_changed_gets_them_back(repo, tmp_path):
    git_dir = str(tmp_path / "snaps.git")
    SnapshotStore(git_dir, str(repo)).ensure()
    attributes = os.path.join(git_dir, "info", "attributes")
    with open(attributes, "w") as f:
        f.write("* filter=lfs\n")

    SnapshotStore(git_dir, str(repo)).ensure()

    with open(attributes) as f:
        assert "-filter" in f.read()
    # No temporary file is left beside it.
    assert not [
        n for n in os.listdir(os.path.dirname(attributes)) if "attributes." in n
    ]
