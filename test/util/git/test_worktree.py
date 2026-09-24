"""Working-tree snapshots: diff exactly what changed between two moments,
without writing anything into the repository."""

import os
import subprocess
import time

import pytest

from zrb.util.git.worktree import (
    GIT_COMMAND_TIMEOUT_SECONDS,
    create_snapshot_store,
    delete_snapshot_store,
    diff_snapshots,
    get_command_timeout,
    get_repo_root,
    snapshot_worktree,
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
def store():
    path = create_snapshot_store()
    yield path
    delete_snapshot_store(path)


def test_diff_covers_only_what_changed_between_snapshots(repo, store):
    (repo / "tracked.txt").write_text("a\nuser wip\n")  # before the turn
    before = snapshot_worktree(str(repo), store)

    (repo / "created.txt").write_text("new\n")  # e.g. written by a shell command
    (repo / "tracked.txt").write_text("A\nuser wip\n")
    _git(repo, "commit", "-qam", "committed mid-turn")
    (repo / "ignored.txt").write_text("secret\n")
    after = snapshot_worktree(str(repo), store)

    assert before and after
    changed = diff_snapshots(str(repo), store, before, after)
    assert changed is not None
    paths, diff = changed
    assert sorted(paths) == ["created.txt", "tracked.txt"]
    assert "+A" in diff and "-a" in diff
    changed_lines = [line[1:] for line in diff.splitlines() if line[:1] in "+-"]
    assert "user wip" not in changed_lines


def test_diff_covers_a_file_deleted_from_the_working_tree(repo, store):
    # Each snapshot starts from an empty index, but a file present at turn
    # start is in the start tree, so its removal shows as a deletion.
    before = snapshot_worktree(str(repo), store)

    (repo / "tracked.txt").unlink()  # e.g. `rm` through a shell command
    after = snapshot_worktree(str(repo), store)

    assert before and after
    changed = diff_snapshots(str(repo), store, before, after)
    assert changed is not None
    paths, diff = changed
    assert paths == ["tracked.txt"]
    assert "deleted file mode" in diff and "-a" in diff


def test_snapshot_writes_nothing_into_the_repository(repo, store):
    (repo / ".env.local").write_text("AWS_SECRET=hunter2\n")  # untracked secret
    objects_before = _loose_objects(repo)

    tree = snapshot_worktree(str(repo), store)

    assert tree
    assert _loose_objects(repo) == objects_before
    secret_blob = _git(repo, "hash-object", ".env.local").stdout.strip()
    assert _git(repo, "cat-file", "-e", secret_blob, check=False).returncode != 0
    assert _git(repo, "status", "--porcelain").stdout.splitlines() == ["?? .env.local"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_store_is_owner_only():
    store = create_snapshot_store()
    try:
        assert os.stat(store).st_mode & 0o077 == 0
    finally:
        delete_snapshot_store(store)


def test_store_is_deleted_with_its_objects(repo):
    store = create_snapshot_store()

    snapshot_worktree(str(repo), store)
    delete_snapshot_store(store)

    assert not os.path.exists(store)


def test_outside_a_repository_everything_is_none(tmp_path, store):
    assert get_repo_root(str(tmp_path)) is None
    assert snapshot_worktree(str(tmp_path), store) is None
    assert diff_snapshots(str(tmp_path), store, "a", "b") is None


def test_command_timeout_is_capped_and_shrinks_toward_the_deadline():
    assert get_command_timeout(None) == GIT_COMMAND_TIMEOUT_SECONDS
    assert get_command_timeout(time.monotonic() + 3600) == GIT_COMMAND_TIMEOUT_SECONDS
    assert 0 < get_command_timeout(time.monotonic() + 5) <= 5
    assert get_command_timeout(time.monotonic() - 1) <= 0


def test_a_passed_deadline_runs_no_git_command(repo, store):
    before = snapshot_worktree(str(repo), store)
    past = time.monotonic() - 1

    assert get_repo_root(str(repo), past) is None
    assert snapshot_worktree(str(repo), store, past) is None
    assert diff_snapshots(str(repo), store, before, before, past) is None


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
def test_unreadable_file_is_left_out_instead_of_failing_the_snapshot(repo, store):
    secret = repo / "secret.key"
    secret.write_text("protected\n")
    secret.chmod(0)
    try:
        before = snapshot_worktree(str(repo), store)
        (repo / "tracked.txt").write_text("changed\n")
        after = snapshot_worktree(str(repo), store)
    finally:
        secret.chmod(0o600)

    assert before and after
    changed = diff_snapshots(str(repo), store, before, after)
    assert changed is not None and changed[0] == ["tracked.txt"]


def test_file_ignored_mid_turn_leaves_later_snapshots(repo, store):
    (repo / " late.txt").write_text("v1\n")  # leading space: -z paths unstripped
    before = snapshot_worktree(str(repo), store)
    (repo / ".gitignore").write_text("ignored.txt\n late.txt\n")
    first = snapshot_worktree(str(repo), store)
    (repo / " late.txt").write_text("v2\n")
    second = snapshot_worktree(str(repo), store)

    assert before and first and second
    assert diff_snapshots(str(repo), store, first, second) == ([], "")
