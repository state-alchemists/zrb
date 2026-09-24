"""Working-tree snapshots: diff exactly what changed between two moments,
without writing anything into the repository."""

import os
import subprocess

import pytest

from zrb.util.git.worktree import (
    create_snapshot_store,
    delete_snapshot_store,
    diff_snapshots,
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
