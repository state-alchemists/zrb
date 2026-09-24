"""SnapshotStore: snapshot a directory as git trees and diff exactly what
changed between two moments, without writing anything into the repository."""

import os
import subprocess
import time

import pytest

from zrb.util.git.snapshot_store import (
    GIT_COMMAND_TIMEOUT_SECONDS,
    SnapshotError,
    SnapshotStore,
    get_command_timeout,
    get_repo_root,
)


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
    tree, _ = store.snapshot()
    return tree


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

        assert get_repo_root(str(workdir)) is None
        assert store.work_tree == os.path.realpath(workdir)
        assert store.diff(before, after)[0] == ["a.txt"]
    finally:
        store.delete()


def test_command_timeout_is_capped_and_shrinks_toward_the_deadline():
    assert get_command_timeout(None) == GIT_COMMAND_TIMEOUT_SECONDS
    assert get_command_timeout(time.monotonic() + 3600) == GIT_COMMAND_TIMEOUT_SECONDS
    assert 0 < get_command_timeout(time.monotonic() + 5) <= 5
    assert get_command_timeout(time.monotonic() - 1) <= 0


def test_a_passed_deadline_runs_no_git_command(repo, store):
    before = _snap(store)
    past = time.monotonic() - 1

    assert get_repo_root(str(repo), past) is None
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


@pytest.mark.skipif(os.name != "posix", reason="non-UTF-8 file names are POSIX-only")
def test_non_utf8_names_and_content_do_not_break_a_snapshot(repo, store):
    before = _snap(store)
    raw_name = os.path.join(os.fsencode(str(repo)), b"latin\xe9.txt")
    with open(raw_name, "wb") as f:
        f.write(b"caf\xe9\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    paths, diff = changed
    assert [os.fsencode(p) for p in paths] == [b"latin\xe9.txt"]
    assert "caf�" in diff


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
    tracked_blob = _git(repo, "hash-object", "tracked.txt").stdout.strip()
    (repo / "untracked.txt").write_text("new\n")
    untracked_blob = _git(repo, "hash-object", "untracked.txt").stdout.strip()

    _snap(store)

    own = os.path.join(store.git_dir, "objects")
    assert not os.path.exists(os.path.join(own, tracked_blob[:2], tracked_blob[2:]))
    assert os.path.exists(os.path.join(own, untracked_blob[:2], untracked_blob[2:]))
