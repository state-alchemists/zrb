"""Working-tree snapshots: diff exactly what changed between two moments,
without touching the repository's own index."""

import subprocess

import pytest

from zrb.util.git.worktree import diff_snapshots, get_repo_root, snapshot_worktree


def _git(repo, *args) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


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


def test_diff_covers_only_what_changed_between_snapshots(repo):
    (repo / "tracked.txt").write_text("a\nuser wip\n")  # before the turn
    before = snapshot_worktree(str(repo))

    (repo / "created.txt").write_text("new\n")  # e.g. written by a shell command
    (repo / "tracked.txt").write_text("A\nuser wip\n")
    _git(repo, "commit", "-qam", "committed mid-turn")
    (repo / "ignored.txt").write_text("secret\n")
    after = snapshot_worktree(str(repo))

    assert before and after
    changed = diff_snapshots(str(repo), before, after)
    assert changed is not None
    paths, diff = changed
    assert sorted(paths) == ["created.txt", "tracked.txt"]
    assert "+A" in diff and "-a" in diff
    assert "user wip" not in [
        line[1:] for line in diff.splitlines() if line[:1] in "+-"
    ]


def test_snapshot_leaves_the_real_index_alone(repo):
    (repo / "untracked.txt").write_text("x\n")

    snapshot_worktree(str(repo))

    assert _git(repo, "status", "--porcelain").splitlines() == ["?? untracked.txt"]


def test_outside_a_repository_everything_is_none(tmp_path):
    assert get_repo_root(str(tmp_path)) is None
    assert snapshot_worktree(str(tmp_path)) is None
    assert diff_snapshots(str(tmp_path), "a", "b") is None
