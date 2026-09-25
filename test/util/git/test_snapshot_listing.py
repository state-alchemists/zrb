"""Which files a working-directory snapshot holds: every repository by its
own rules, nested ones included, and loose files up to a budget."""

import os
import subprocess

import pytest

from zrb.util.git import snapshot_listing
from zrb.util.git.snapshot_listing import (
    SnapshotBudgetError,
    get_out_of_scope_paths,
    get_worktree_fork_point,
    list_snapshot_paths,
)


def _git(cwd, *args) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(path, files: dict[str, str], commit: bool = True):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    for name, content in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(content)
    if commit:
        _git(path, "add", ".")
        _git(path, "commit", "-qm", "init")
    return path


@pytest.fixture(autouse=True)
def _no_enclosing_repository(tmp_path, monkeypatch):
    # The temp dir must not count as inside whatever repository holds it.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def test_a_repository_is_listed_by_its_own_ignore_rules(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n", ".gitignore": "build/\n"})
    (repo / "build").mkdir()
    (repo / "build" / "out.bin").write_text("x\n")
    (repo / "new.py").write_text("n\n")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "dep.js").write_text("d\n")

    listing = list_snapshot_paths(str(repo))

    assert sorted(listing.paths) == [".gitignore", "a.py", "new.py"]
    assert listing.repositories == [""]


def test_a_subdirectory_honours_the_ignore_rules_above_it(tmp_path):
    repo = _repo(tmp_path / "r", {".gitignore": "*.log\n", "pkg/a.py": "a\n"})
    (repo / "pkg" / "debug.log").write_text("x\n")
    (repo / "top.py").write_text("t\n")

    listing = list_snapshot_paths(str(repo / "pkg"))

    assert listing.paths == ["a.py"]


def test_a_nested_repository_is_listed_by_itself(tmp_path):
    # The parent ignores `*.log`, the nested repositories do not: their own
    # rules decide, so their logs are listed and the parent's is not.
    repo = _repo(tmp_path / "r", {"app.py": "x\n", ".gitignore": "*.log\n"})
    (repo / "debug.log").write_text("x\n")
    _repo(repo / "vendor" / "lib", {"v.py": "v\n", ".gitignore": "junk/\n"})
    (repo / "vendor" / "lib" / "junk").mkdir()
    (repo / "vendor" / "lib" / "junk" / "big").write_text("x\n")
    (repo / "vendor" / "lib" / "run.log").write_text("x\n")
    _repo(repo / "fresh", {"f.py": "f\n"}, commit=False)
    (repo / "fresh" / "fresh.log").write_text("x\n")

    listing = list_snapshot_paths(str(repo))

    assert sorted(listing.paths) == [
        ".gitignore",
        "app.py",
        "fresh/f.py",
        "fresh/fresh.log",
        "vendor/lib/.gitignore",
        "vendor/lib/run.log",
        "vendor/lib/v.py",
    ]
    assert sorted(listing.repositories) == ["", "fresh", "vendor/lib"]


def test_a_submodule_is_listed_by_itself(tmp_path):
    upstream = _repo(tmp_path / "upstream", {"s.py": "s\n"})
    repo = _repo(tmp_path / "r", {"app.py": "x\n"})
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

    listing = list_snapshot_paths(str(repo))

    assert "sm/s.py" in listing.paths
    assert "sm" not in listing.paths


def test_a_directory_of_repositories_lists_each_and_its_loose_files(tmp_path):
    workspace = tmp_path / "ws"
    _repo(workspace / "a", {"x.py": "a\n"})
    _repo(workspace / "b", {"y.py": "b\n"})
    (workspace / "notes.txt").write_text("n\n")
    (workspace / ".venv").mkdir()
    (workspace / ".venv" / "lib.py").write_text("v\n")

    listing = list_snapshot_paths(str(workspace))

    assert sorted(listing.paths) == ["a/x.py", "b/y.py", "notes.txt"]
    assert sorted(listing.repositories) == ["a", "b"]


def test_a_repository_the_parent_ignores_stays_out(tmp_path):
    repo = _repo(tmp_path / "r", {".gitignore": "vendor/\n"})
    _repo(repo / "vendor" / "lib", {"v.py": "v\n"})

    assert list_snapshot_paths(str(repo)).paths == [".gitignore"]


def test_excluded_paths_are_left_out_everywhere(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    (repo / "store.git").mkdir()
    (repo / "store.git" / "HEAD").write_text("ref\n")

    listing = list_snapshot_paths(str(repo), exclude_paths=[str(repo / "store.git")])

    assert listing.paths == ["a.py"]


def test_loose_files_past_the_budget_fail_the_listing(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot_listing, "LOOSE_FILE_LIMIT", 3)
    workspace = tmp_path / "ws"
    for i in range(4):
        (workspace / f"d{i}").mkdir(parents=True)
        (workspace / f"d{i}" / "f.txt").write_text("x\n")

    with pytest.raises(SnapshotBudgetError, match="more than 3 files"):
        list_snapshot_paths(str(workspace))


def test_files_inside_repositories_do_not_count_toward_the_budget(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(snapshot_listing, "LOOSE_FILE_LIMIT", 1)
    workspace = tmp_path / "ws"
    _repo(workspace / "a", {f"f{i}.py": "x\n" for i in range(5)})

    assert len(list_snapshot_paths(str(workspace)).paths) == 5


def test_loose_bytes_past_the_budget_fail_the_listing(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot_listing, "LOOSE_BYTE_LIMIT", 10)
    (tmp_path / "ws").mkdir()
    (tmp_path / "ws" / "big.bin").write_bytes(b"x" * 11)

    with pytest.raises(SnapshotBudgetError, match="MB of files"):
        list_snapshot_paths(str(tmp_path / "ws"))


def _worktree(repo, branch: str):
    path = repo / ".zrb" / "worktree" / branch
    (repo / ".gitignore").write_text(".zrb/worktree/\n")
    _git(repo, "worktree", "add", "-q", "-b", branch, str(path))
    return path


def test_linked_worktrees_are_listed_only_when_asked(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    worktree = _worktree(repo, "wt")
    (worktree / "b.py").write_text("b\n")

    plain = list_snapshot_paths(str(repo))
    with_worktrees = list_snapshot_paths(str(repo), include_worktrees=True)

    assert ".zrb/worktree/wt/b.py" not in plain.paths
    assert ".zrb/worktree/wt/a.py" in with_worktrees.paths
    assert ".zrb/worktree/wt/b.py" in with_worktrees.paths
    assert with_worktrees.worktrees == [".zrb/worktree/wt"]


def test_a_worktree_whose_repository_is_gone_is_walked(tmp_path):
    workspace = tmp_path / "ws"
    orphan = workspace / "copy"
    orphan.mkdir(parents=True)
    (orphan / ".git").write_text("gitdir: /nowhere/.git/worktrees/copy\n")
    (orphan / "c.py").write_text("c\n")

    assert list_snapshot_paths(str(workspace)).paths == ["copy/c.py"]


def test_a_worktree_fork_point_is_the_commit_it_was_created_at(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    base = _git(repo, "rev-parse", "HEAD").strip()
    worktree = _worktree(repo, "wt")
    (worktree / "b.py").write_text("b\n")
    _git(worktree, "add", "b.py")
    _git(worktree, "commit", "-qm", "b")

    assert get_worktree_fork_point(str(worktree)) == base


def test_out_of_scope_paths_follow_each_repositorys_rules_now(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n", ".gitignore": "*.log\nbuild/\n"})
    _repo(repo / "lib", {"v.py": "v\n", ".gitignore": "secret\n"})
    paths = [
        "a.py",
        "old.log",
        "gone.py",
        "build/out.o",
        "lib/secret",
        "lib/v.py",
        ".venv/x",
    ]

    out = get_out_of_scope_paths(str(repo), paths, ["", "lib"])

    assert out == {"old.log", "build/out.o", "lib/secret", ".venv/x"}


@pytest.mark.skipif(os.name != "posix", reason="symlinks need privileges on Windows")
def test_a_symlinked_directory_outside_git_is_listed_as_a_link(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "real").mkdir(parents=True)
    (workspace / "real" / "f.txt").write_text("x\n")
    os.symlink(workspace / "real", workspace / "link")

    assert sorted(list_snapshot_paths(str(workspace)).paths) == ["link", "real/f.txt"]
