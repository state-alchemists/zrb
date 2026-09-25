"""SnapshotStore: snapshot a directory as git trees, diff exactly what changed
between two moments, and restore one — nested repositories included — without
writing anything into any repository."""

import os
import shutil
import subprocess
import time

import pytest

from zrb.util.git.snapshot_command import SnapshotError
from zrb.util.git.snapshot_store import SnapshotStore


def _git(repo, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )


def _loose_objects(repo) -> set[str]:
    objects = repo / ".git" / "objects"
    return {
        str(path.relative_to(objects))
        for path in objects.rglob("*")
        if path.is_file() and path.parent.name not in ("pack", "info")
    }


@pytest.fixture(autouse=True)
def _no_enclosing_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _nested(path, files: dict[str, str]):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    for name, content in files.items():
        (path / name).write_text(content)
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tracked.txt").write_text("a\n")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


@pytest.fixture
def store(repo):
    snapshots = SnapshotStore.create_temporary(str(repo))
    yield snapshots
    snapshots.delete()


def _snap(store: SnapshotStore) -> str:
    return store.snapshot().tree


def test_diff_covers_only_what_changed_between_snapshots(repo, store):
    (repo / "tracked.txt").write_text("a\nuser wip\n")  # before the turn
    before = _snap(store)

    (repo / "created.txt").write_text("new\n")  # e.g. written by a shell command
    (repo / "tracked.txt").write_text("A\nuser wip\n")
    _git(repo, "commit", "-qam", "committed mid-turn")
    (repo / "ignored.txt").write_text("secret\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    paths, diff = changed
    assert sorted(paths) == ["created.txt", "tracked.txt"]
    assert "+A" in diff and "-a" in diff
    changed_lines = [line[1:] for line in diff.splitlines() if line[:1] in "+-"]
    assert "user wip" not in changed_lines


def test_diff_covers_a_file_deleted_from_the_working_tree(repo, store):
    # A file present at turn start is in the start tree, so its removal
    # shows as a deletion.
    before = _snap(store)

    (repo / "tracked.txt").unlink()  # e.g. `rm` through a shell command
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    paths, diff = changed
    assert paths == ["tracked.txt"]
    assert "deleted file mode" in diff and "-a" in diff


def test_snapshot_writes_nothing_into_the_repository(repo, store):
    (repo / ".env.local").write_text("AWS_SECRET=hunter2\n")  # untracked secret
    objects_before = _loose_objects(repo)

    tree = _snap(store)

    assert tree
    assert _loose_objects(repo) == objects_before
    secret_blob = _git(repo, "hash-object", ".env.local").stdout.strip()
    assert _git(repo, "cat-file", "-e", secret_blob, check=False).returncode != 0
    assert _git(repo, "status", "--porcelain").stdout.splitlines() == ["?? .env.local"]


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


def test_outside_a_repository_the_directory_itself_is_snapshotted(tmp_path):
    workdir = tmp_path / "project"
    (workdir / "node_modules").mkdir(parents=True)
    (workdir / "a.txt").write_text("a\n")
    store = SnapshotStore.create_temporary(str(workdir))
    try:
        before = _snap(store)
        (workdir / "a.txt").write_text("b\n")
        (workdir / "node_modules" / "dep.js").write_text("x\n")
        after = _snap(store)

        assert store.work_tree == os.path.realpath(workdir)
        assert store.diff(before, after)[0] == ["a.txt"]
    finally:
        store.delete()


def test_a_passed_deadline_runs_no_git_command(repo, store):
    before = _snap(store)
    past = time.monotonic() - 1

    with pytest.raises(SnapshotError):
        store.snapshot(past)
    with pytest.raises(SnapshotError):
        store.diff(before, before, past)


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
def test_unreadable_file_is_left_out_instead_of_failing_the_snapshot(repo, store):
    secret = repo / "secret.key"
    secret.write_text("protected\n")
    secret.chmod(0)
    try:
        before = _snap(store)
        (repo / "tracked.txt").write_text("changed\n")
        after = _snap(store)
    finally:
        secret.chmod(0o600)

    assert before and after
    changed = store.diff(before, after)
    assert changed[0] == ["tracked.txt"]


def test_file_ignored_mid_turn_leaves_later_snapshots(repo, store):
    (repo / " late.txt").write_text("v1\n")  # leading space: -z paths unstripped
    before = _snap(store)
    (repo / ".gitignore").write_text("ignored.txt\n late.txt\n")
    first = _snap(store)
    (repo / " late.txt").write_text("v2\n")
    second = _snap(store)

    assert before and first and second
    assert store.diff(first, second) == ([], "")


def test_changed_paths_are_exact_for_unusual_names(repo, store):
    names = ["café.txt", " lead.txt", "tab\there.txt", 'quo"te.txt']
    if os.name == "nt":
        names = names[:2]
    before = _snap(store)
    for name in names:
        (repo / name).write_text("x\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert sorted(changed[0]) == sorted(names)


def test_a_rename_lists_both_its_old_and_new_path(repo, store):
    before = _snap(store)
    (repo / "tracked.txt").rename(repo / "moved.txt")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert sorted(changed[0]) == ["moved.txt", "tracked.txt"]


def test_non_utf8_content_does_not_break_a_diff(repo, store):
    before = _snap(store)
    (repo / "latin.txt").write_bytes(b"caf\xe9\n")
    after = _snap(store)

    paths, diff = store.diff(before, after)
    assert paths == ["latin.txt"]
    assert "caf\ufffd" in diff


@pytest.mark.skipif(os.name != "posix", reason="non-UTF-8 file names are POSIX-only")
def test_a_non_utf8_file_name_survives_a_snapshot(repo, store):
    raw_name = os.path.join(os.fsencode(str(repo)), b"latin\xe9.txt")
    try:
        with open(raw_name, "wb") as f:
            f.write(b"x\n")
    except OSError:
        # macOS (APFS) refuses a name that is not valid UTF-8 outright, so the
        # case cannot arise there.
        pytest.skip("this filesystem rejects non-UTF-8 file names")
    os.remove(raw_name)
    before = _snap(store)
    with open(raw_name, "wb") as f:
        f.write(b"x\n")
    after = _snap(store)

    paths, _ = store.diff(before, after)
    assert [os.fsencode(p) for p in paths] == [b"latin\xe9.txt"]


def test_the_diff_ignores_the_users_external_diff_and_colour(repo, store):
    _git(repo, "config", "diff.external", "false")
    _git(repo, "config", "color.ui", "always")
    before = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert "-a\n+b" in changed[1]
    assert "\x1b[" not in changed[1]


def test_a_store_inside_the_repository_is_not_snapshotted(repo):
    store = SnapshotStore(str(repo / "tmp-store"), str(repo), borrow_objects=True)
    before = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert changed[0] == ["tracked.txt"]


def test_the_repositorys_own_info_exclude_applies(repo, store):
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "exclude").write_text("local-notes.txt\n")
    before = _snap(store)
    (repo / "local-notes.txt").write_text("private\n")
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert store.diff(before, after)[0] == ["tracked.txt"]


def test_inherited_git_variables_cannot_redirect_a_snapshot(repo, store, monkeypatch):
    # e.g. zrb started from inside a git hook, which exports these.
    monkeypatch.setenv("GIT_INDEX_FILE", str(repo / "elsewhere-index"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(repo / "elsewhere-objects"))
    monkeypatch.setenv("GIT_DIR", str(repo / "not-a-repo"))
    before = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert store.diff(before, after)[0] == ["tracked.txt"]
    assert not (repo / "elsewhere-index").exists()
    assert not (repo / "elsewhere-objects").exists()


def test_a_temporary_store_borrows_tracked_objects_instead_of_copying(repo, store):
    # Written as bytes, and hashed without filters: on Windows `write_text`
    # would add CRLF, and the repository's `core.autocrlf` would hash that
    # differently from the store, which stores bytes exactly.
    (repo / "committed.txt").write_bytes(b"committed\n")
    _git(repo, "add", "committed.txt")
    _git(repo, "commit", "-qm", "add committed")
    (repo / "untracked.txt").write_bytes(b"new\n")
    tracked_blob = _git(
        repo, "hash-object", "--no-filters", "committed.txt"
    ).stdout.strip()
    untracked_blob = _git(
        repo, "hash-object", "--no-filters", "untracked.txt"
    ).stdout.strip()

    _snap(store)

    own = os.path.join(store.git_dir, "objects")
    assert not os.path.exists(os.path.join(own, tracked_blob[:2], tracked_blob[2:]))
    assert os.path.exists(os.path.join(own, untracked_blob[:2], untracked_blob[2:]))


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


def test_changes_inside_a_nested_repository_are_diffed(repo, store):
    lib = _nested(repo / "vendor" / "lib", {"v.py": "v\n"})
    before = _snap(store)

    (lib / "v.py").write_text("changed\n")  # e.g. `sed -i` through a shell
    after = _snap(store)

    assert store.diff(before, after)[0] == ["vendor/lib/v.py"]
    assert _git(lib, "status", "--porcelain").stdout == " M v.py\n"


def test_a_directory_of_repositories_is_diffed_as_one(tmp_path):
    workspace = tmp_path / "ws"
    a = _nested(workspace / "a", {"x.py": "a\n"})
    b = _nested(workspace / "b", {"y.py": "b\n"})
    (workspace / "notes.txt").write_text("n\n")
    store = SnapshotStore.create_temporary(str(workspace))
    try:
        before = _snap(store)
        (a / "x.py").write_text("A\n")
        (b / "y.py").unlink()
        (workspace / "notes.txt").write_text("N\n")
        after = _snap(store)

        assert sorted(store.diff(before, after)[0]) == ["a/x.py", "b/y.py", "notes.txt"]
    finally:
        store.delete()


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


def test_a_temporary_store_borrows_a_nested_repositorys_objects(repo, store):
    lib = _nested(repo / "lib", {"v.py": "v\n"})
    blob = _git(lib, "hash-object", "--no-filters", "v.py").stdout.strip()

    _snap(store)

    own = os.path.join(store.git_dir, "objects")
    assert not os.path.exists(os.path.join(own, blob[:2], blob[2:]))


def test_a_snapshot_reports_the_repositories_it_holds(repo, store):
    (repo / ".gitignore").write_text("ignored.txt\n.zrb/worktree/\n")
    worktree = repo / ".zrb" / "worktree" / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    _nested(repo / "lib", {"v.py": "v\n"})

    snapshot = store.snapshot()

    assert sorted(snapshot.repositories) == ["", ".zrb/worktree/wt", "lib"]
