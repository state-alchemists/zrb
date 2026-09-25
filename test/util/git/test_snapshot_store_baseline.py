"""SnapshotStore.create_repository_baseline: a repository that appeared
during a turn, as its own checkout of the commit it started from wrote it."""

import subprocess

import pytest

from zrb.util.git.snapshot_store import SnapshotStore


def _git(repo, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


@pytest.fixture(autouse=True)
def _no_enclosing_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _snap(store: SnapshotStore) -> str:
    return store.snapshot().tree


@pytest.mark.parametrize(
    "autocrlf, attributes, checked_out",
    [
        ("false", b"", b"a\n"),
        ("true", b"", b"a\r\n"),
        # Chosen by path: `<commit>:<path>` names the blob and the path.
        ("false", b"*.txt text eol=crlf\n", b"a\r\n"),
    ],
)
def test_a_repository_baseline_holds_what_its_own_checkout_wrote(
    repo, store, autocrlf, attributes, checked_out
):
    _git(repo, "config", "core.autocrlf", autocrlf)
    (repo / ".gitattributes").write_bytes(attributes)
    (repo / ".gitignore").write_bytes(b"ignored.txt\n.zrb/worktree/\n")
    (repo / "gone.txt").write_bytes(b"g\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "more")
    fork = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _snap(store)
    worktree = repo / ".zrb" / "worktree" / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    (worktree / "tracked.txt").write_bytes(b"changed\n")
    (worktree / "gone.txt").unlink()
    (worktree / "new.txt").write_bytes(b"n\n")
    (worktree / "committed.txt").write_bytes(b"c\n")
    _git(worktree, "add", "committed.txt")
    _git(worktree, "commit", "-qm", "added since the fork")
    after = store.snapshot()

    baseline = store.create_repository_baseline(before, after, ".zrb/worktree/wt", fork)

    paths, diff = store.diff(baseline, after.tree)
    assert sorted(paths) == [
        ".zrb/worktree/wt/committed.txt",
        ".zrb/worktree/wt/gone.txt",
        ".zrb/worktree/wt/new.txt",
        ".zrb/worktree/wt/tracked.txt",
    ]
    assert "-a" in diff and "+changed" in diff
    assert "+c" in diff  # added and committed since the fork: shown as added
    tracked = f"{baseline}:.zrb/worktree/wt/tracked.txt"
    show = ["git", "--git-dir", store.git_dir, "show", tracked]
    assert subprocess.run(show, capture_output=True).stdout == checked_out


def test_a_repository_baseline_leaves_out_what_the_listing_leaves_out(repo, store):
    (repo / ".gitignore").write_bytes(b"ignored.txt\n.zrb/worktree/\n")
    (repo / ".cache").mkdir()
    (repo / ".cache" / "c.txt").write_bytes(b"c\n")
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-qm", "tracked cache")
    fork = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _snap(store)
    worktree = repo / ".zrb" / "worktree" / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    (worktree / ".cache" / "c.txt").write_bytes(b"changed\n")  # never listed
    after = store.snapshot()

    baseline = store.create_repository_baseline(before, after, ".zrb/worktree/wt", fork)

    assert store.diff(baseline, after.tree)[0] == []
