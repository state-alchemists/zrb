"""Which files a working-directory snapshot holds: every repository by its
own rules, nested ones included, and loose files up to a budget."""

import os
import socket
import subprocess

import pytest

from zrb.util.git import snapshot_listing
from zrb.util.git.snapshot_command import SnapshotError
from zrb.util.git.snapshot_listing import (
    SnapshotBudgetError,
    get_fork_point,
    get_out_of_scope_paths,
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
    # What it leaves out, as git reports it: `DEFAULT_IGNORE_DIRS` too.
    assert sorted(listing.left_out) == ["build/", "node_modules/"]


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


def test_a_repository_inside_an_ignored_directory_is_listed_by_itself(tmp_path):
    # The parent ignores `vendor/` so it stops reporting the clones in it;
    # the clones' own rules decide their files, and nothing else in the
    # ignored directory is listed.
    repo = _repo(tmp_path / "r", {".gitignore": "vendor/\nbuild/\n"})
    _repo(repo / "vendor" / "libs" / "a", {"a.py": "a\n", ".gitignore": "*.tmp\n"})
    (repo / "vendor" / "libs" / "a" / "x.tmp").write_text("x\n")
    (repo / "vendor" / "README").write_text("r\n")
    (repo / "build" / "out").mkdir(parents=True)
    (repo / "build" / "out" / "app.o").write_text("o\n")

    listing = list_snapshot_paths(str(repo))

    assert sorted(listing.paths) == [
        ".gitignore",
        "vendor/libs/a/.gitignore",
        "vendor/libs/a/a.py",
    ]
    assert sorted(listing.repositories) == ["", "vendor/libs/a"]


def test_no_repository_is_searched_for_under_a_default_ignored_directory(
    tmp_path,
):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    _repo(repo / "node_modules" / "pkg", {"p.js": "p\n"})

    assert list_snapshot_paths(str(repo)).paths == ["a.py"]


def test_a_broken_repository_inside_an_ignored_directory_is_left_out(tmp_path):
    repo = _repo(tmp_path / "r", {".gitignore": "old/\n"})
    (repo / "old" / "copy").mkdir(parents=True)
    (repo / "old" / "copy" / ".git").write_text("gitdir: /nowhere\n")
    (repo / "old" / "copy" / "c.py").write_text("c\n")

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


def test_a_linked_worktree_the_repository_ignores_is_listed(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    worktree = _worktree(repo, "wt")
    (worktree / "b.py").write_text("b\n")

    listing = list_snapshot_paths(str(repo))

    assert ".zrb/worktree/wt/a.py" in listing.paths
    assert ".zrb/worktree/wt/b.py" in listing.paths
    assert ".zrb/worktree/wt" in listing.repositories


def test_a_worktree_whose_repository_is_gone_is_walked(tmp_path):
    workspace = tmp_path / "ws"
    orphan = workspace / "copy"
    orphan.mkdir(parents=True)
    (orphan / ".git").write_text("gitdir: /nowhere/.git/worktrees/copy\n")
    (orphan / "c.py").write_text("c\n")

    assert list_snapshot_paths(str(workspace)).paths == ["copy/c.py"]


def test_a_fork_point_is_the_commit_a_repository_started_from(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    base = _git(repo, "rev-parse", "HEAD").strip()
    worktree = _worktree(repo, "wt")
    _git(tmp_path, "clone", "-q", str(repo), str(tmp_path / "clone"))
    for checkout in (worktree, tmp_path / "clone"):
        (checkout / "b.py").write_text("b\n")
        _git(checkout, "add", "b.py")
        _git(checkout, "commit", "-qm", "b")

    assert get_fork_point(str(worktree)) == base
    assert get_fork_point(str(tmp_path / "clone")) == base
    assert get_fork_point(str(_repo(tmp_path / "new", {}, commit=False))) is None
    # A repository born with its first commit started from nothing too —
    # also when a tool committing for the user replaced the reflog subject.
    assert get_fork_point(str(_repo(tmp_path / "born", {"b.py": "b\n"}))) is None
    tool = tmp_path / "tool"
    tool.mkdir()
    _git(tool, "init", "-q")
    (tool / "t.py").write_text("t\n")
    _git(tool, "add", ".")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "1"],
        cwd=tool,
        check=True,
        env={**os.environ, "GIT_REFLOG_ACTION": "some-tool: import"},
    )
    assert get_fork_point(str(tool)) is None


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


def test_a_tracked_file_matching_an_ignore_pattern_stays_in_scope(tmp_path):
    repo = _repo(tmp_path / "r", {".gitignore": ".env*\n"})
    (repo / ".env.example").write_text("KEY=\n")
    _git(repo, "add", "-f", ".env.example")
    _git(repo, "commit", "-qm", "example")

    out = get_out_of_scope_paths(str(repo), [".env.example", ".env"], [""])

    assert ".env.example" in list_snapshot_paths(str(repo)).paths
    assert out == {".env"}


def test_a_working_directory_its_repository_ignores_is_walked(tmp_path):
    repo = _repo(tmp_path / "r", {".gitignore": "scratch/\n"})
    (repo / "scratch").mkdir()
    (repo / "scratch" / "try.py").write_text("t\n")
    _repo(repo / "scratch" / "lib", {"v.py": "v\n"})

    listing = list_snapshot_paths(str(repo / "scratch"))

    assert sorted(listing.paths) == ["lib/v.py", "try.py"]
    assert listing.repositories == ["lib"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
def test_a_walk_lists_only_what_git_can_store(tmp_path, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("a\n")
    try:
        os.mkfifo(workspace / "pipe")
    except OSError:
        pytest.skip("this filesystem cannot hold a FIFO")
    sock = socket.socket(socket.AF_UNIX)
    # Bound by a relative name: macOS caps a socket path at 104 bytes, and
    # its temporary directory alone takes most of them.
    monkeypatch.chdir(workspace)
    try:
        sock.bind("sock")
        assert list_snapshot_paths(str(workspace)).paths == ["a.txt"]
    finally:
        sock.close()


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows feature")
def test_a_walk_does_not_follow_a_junction(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "far.txt").write_text("f\n")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("a\n")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(workspace / "link"), str(outside)],
        check=True,
        capture_output=True,
    )

    assert list_snapshot_paths(str(workspace)).paths == ["a.txt"]


needs_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)


@needs_permissions
def test_a_directory_that_cannot_be_read_is_recorded_as_left_out(tmp_path):
    repo = _repo(tmp_path / "r", {"a.py": "a\n"})
    loose = tmp_path / "loose"
    for top in (repo, loose):
        (top / "volume").mkdir(parents=True)
        (top / "volume" / "data").write_text("d\n")
        (top / "volume").chmod(0)
    try:
        in_repository = list_snapshot_paths(str(repo))
        outside = list_snapshot_paths(str(loose))
    finally:
        for top in (repo, loose):
            (top / "volume").chmod(0o755)

    assert in_repository.left_out == ["volume/"]
    assert outside.left_out == ["volume/"]
    assert outside.paths == []


@needs_permissions
def test_a_working_directory_that_cannot_be_read_is_not_listed_as_empty(tmp_path):
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "a.txt").write_text("a\n")
    loose.chmod(0o300)  # enterable, not listable
    try:
        with pytest.raises(SnapshotError):
            list_snapshot_paths(str(loose))
    finally:
        loose.chmod(0o755)


@needs_permissions
def test_an_unreadable_directory_in_a_repository_under_an_ignored_one_is_found(
    tmp_path,
):
    repo = _repo(tmp_path / "r", {".gitignore": "worktrees/\n"})
    feature = _repo(repo / "worktrees" / "feature", {"f.py": "f\n"})
    (feature / "volume").mkdir()
    (feature / "volume").chmod(0)
    try:
        listing = list_snapshot_paths(str(repo))
    finally:
        (feature / "volume").chmod(0o755)

    assert "worktrees/feature/volume/" in listing.left_out


def test_a_default_ignored_directory_is_not_walked_for_ignored_files(tmp_path):
    repo = _repo(tmp_path / "r", {".gitignore": "*.log\n"})
    (repo / "node_modules" / "pkg").mkdir(parents=True)  # not in .gitignore
    (repo / "node_modules" / "pkg" / "debug.log").write_text("d\n")

    listing = list_snapshot_paths(str(repo))

    assert listing.left_out == ["node_modules/"]


@pytest.mark.parametrize("walk", ["the directory walk", "the search for repositories"])
def test_a_directory_walk_stops_at_the_deadline(tmp_path, monkeypatch, walk):
    loose = tmp_path / "loose"
    (loose / "a").mkdir(parents=True)
    repo = _repo(tmp_path / "r", {".gitignore": "build/\n"})
    (repo / "build" / "deep").mkdir(parents=True)
    real = snapshot_listing.get_time_left

    def out_of_time_for(label_to_stop):
        def get_time_left(deadline, label):
            if label == label_to_stop:
                raise SnapshotError(f"No time left to run {label}")
            return real(deadline, label)

        return get_time_left

    monkeypatch.setattr(snapshot_listing, "get_time_left", out_of_time_for(walk))

    with pytest.raises(SnapshotError):
        list_snapshot_paths(str(loose if walk == "the directory walk" else repo))
