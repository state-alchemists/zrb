"""What the self-review gate reviews: the working directory's diff since the
turn-start snapshot, every repository under it included, plus the file tools'
paths the diff does not cover."""

import os
import subprocess
import time

import pytest

from zrb.llm.hook.manager import HookManager

_FINDINGS = "## Finding\n\n**Problem:** off by one.\n\nRequest changes"


@pytest.mark.asyncio
async def test_without_a_turn_start_snapshot_only_the_paths_are_reviewed(
    tmp_path, monkeypatch, gate, stop
):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", "a.py")
    git("commit", "-qm", "init")
    (tmp_path / "a.py").write_text("x = 2\n")
    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=("a.py", "new.py"))

    # The reviewer gets a request, not the transcript — and no diff against
    # HEAD, which would carry the user's uncommitted work from before the turn.
    request = seen[0].event_data
    assert isinstance(request, str)
    assert "- a.py" in request and "- new.py" in request
    assert "x = 2" not in request
    assert "No diff of this turn's changes is available." in request
    assert "read it directly" in request


@pytest.mark.asyncio
async def test_turn_start_snapshot_scopes_the_review_to_this_turn(
    tmp_path, monkeypatch, start_snapshot, gate, stop
):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    git("add", ".")
    git("commit", "-qm", "init")
    (tmp_path / "a.py").write_text("x = 1\nuser_wip = True\n")
    monkeypatch.chdir(tmp_path)
    before = start_snapshot(tmp_path)
    # A shell command's edit: no file tool names it.
    (tmp_path / "gen.py").write_text("y = 2\n")
    # A file tool's edit git ignores.
    (tmp_path / "ignored.txt").write_text("z\n")
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=("ignored.txt",), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- gen.py" in request and "+y = 2" in request
    assert "- ignored.txt" in request
    assert "Diff against the start of this turn" in request
    assert "- a.py" not in request and "user_wip" not in request


@pytest.mark.asyncio
async def test_a_turn_with_no_changes_since_its_start_is_not_reviewed(
    tmp_path, monkeypatch, start_snapshot, gate, stop, blocked
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    before = start_snapshot(tmp_path)
    manager = HookManager(search_dirs=[])

    with gate(report=_FINDINGS) as (seen, _):
        results = await stop(manager, changed_paths=(), turn_start_snapshot=before)

    assert seen == []
    assert blocked(results) == []


@pytest.mark.asyncio
async def test_slow_git_cannot_stretch_a_review_past_its_timeout(
    tmp_path, monkeypatch, start_snapshot, gate, stop, blocked
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    before = start_snapshot(tmp_path)
    real_run = subprocess.run
    timeouts: list[float] = []

    def hanging_git(args, *rest, timeout=None, **kwargs):
        # Every git command hangs until its own timeout. Patched in-process:
        # a fake `git` script in a temp dir cannot run where it is noexec.
        if args[0] != "git":
            return real_run(args, *rest, timeout=timeout, **kwargs)
        timeouts.append(timeout)
        time.sleep(timeout)
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(subprocess, "run", hanging_git)
    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])

    with gate(report=_FINDINGS, timeout=1) as (seen, _):
        started = time.monotonic()
        results = await stop(manager, turn_start_snapshot=before)
        elapsed = time.monotonic() - started

    assert elapsed < 5
    # Each command got only the time left before the deadline, not 30s.
    assert timeouts and max(timeouts) <= 1
    assert seen == []
    assert blocked(results) == []


@pytest.mark.asyncio
async def test_a_tool_path_under_home_matches_its_tree_path(
    tmp_path, monkeypatch, start_snapshot, gate, stop
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    before = start_snapshot(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=("~/a.py",), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- a.py" in request
    assert "- ~/a.py" not in request


@pytest.mark.asyncio
async def test_outside_git_the_review_still_gets_the_turns_diff(
    tmp_path, monkeypatch, start_snapshot, gate, stop
):
    """The store's work tree is the directory itself when there is no
    repository, so a shell command's edit is still diffed."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    workdir = tmp_path / "project"
    workdir.mkdir()
    (workdir / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(workdir)
    before = start_snapshot(workdir)
    (workdir / "a.py").write_text("x = 2\n")  # through a shell command
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=(), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- a.py" in request and "+x = 2" in request
    assert "Diff against the start of this turn" in request


@pytest.mark.asyncio
async def test_a_nested_repositorys_changes_are_reviewed(
    tmp_path, monkeypatch, start_snapshot, gate, stop
):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    workspace = tmp_path / "ws"
    for repo in ("a", "b"):
        (workspace / repo).mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=workspace / repo, check=True)
    monkeypatch.chdir(workspace)
    before = start_snapshot(workspace)
    (workspace / "a" / "x.py").write_text("x = 1\n")  # e.g. `cd a && ...`
    (workspace / "b" / "y.py").write_text("y = 2\n")
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=(), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- a/x.py" in request and "- b/y.py" in request
    assert "+x = 1" in request and "+y = 2" in request


@pytest.mark.asyncio
@pytest.mark.parametrize("autocrlf", ["false", "true"])
async def test_a_worktree_created_mid_turn_shows_only_what_the_turn_changed(
    tmp_path, monkeypatch, start_snapshot, gate, stop, autocrlf
):
    """With `core.autocrlf` on — the default on Windows — the checkout's bytes
    differ from the commit's, and must still read as unchanged."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    def git(cwd, *args):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
        )

    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", autocrlf)
    (repo / "app.py").write_bytes(b"x = 1\n")
    (repo / ".gitignore").write_bytes(b".zrb/worktree/\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    monkeypatch.chdir(repo)
    before = start_snapshot(repo)
    worktree = repo / ".zrb" / "worktree" / "wt"
    git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))  # EnterWorktree
    (worktree / "app.py").write_bytes(b"x = 2\n")
    (worktree / "new.py").write_bytes(b"n = 1\n")
    git(worktree, "add", ".")
    git(worktree, "commit", "-qm", "work")  # committed in the worktree
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=(), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- .zrb/worktree/wt/app.py" in request
    assert "- .zrb/worktree/wt/new.py" in request
    assert "- .zrb/worktree/wt/.gitignore" not in request  # checked out, unchanged
    assert "-x = 1" in request and "+x = 2" in request


@pytest.mark.asyncio
@pytest.mark.parametrize("committed", [False, True])
async def test_a_repository_started_mid_turn_shows_all_its_files(
    tmp_path, monkeypatch, start_snapshot, gate, stop, committed
):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("repos/\n")
    monkeypatch.chdir(repo)
    before = start_snapshot(repo)
    child = repo / "repos" / "new"
    child.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=child, check=True)
    (child / "main.py").write_text("m = 1\n")
    if committed:  # its first commit is the turn's work too
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
            cwd=child,
            check=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "1"],
            cwd=child,
            check=True,
        )
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=(), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- repos/new/main.py" in request and "+m = 1" in request


@pytest.mark.asyncio
async def test_a_diff_that_fails_on_the_filesystem_falls_back_to_the_paths(
    tmp_path, monkeypatch, start_snapshot, gate, stop
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    before = start_snapshot(tmp_path)

    def refuse(store, deadline=None):
        raise PermissionError("index copy refused")

    monkeypatch.setattr("zrb.llm.hook.self_review.SnapshotStore.snapshot", refuse)
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=("a.py",), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- a.py" in request
    assert "No diff of this turn's changes is available." in request


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
async def test_a_file_unreadable_at_stop_is_listed_not_shown_as_deleted(
    tmp_path, monkeypatch, start_snapshot, gate, stop
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "locked.txt").write_text("l\n")
    monkeypatch.chdir(tmp_path)
    before = start_snapshot(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "locked.txt").chmod(0)
    manager = HookManager(search_dirs=[])
    try:
        with gate() as (seen, _):
            await stop(manager, changed_paths=(), turn_start_snapshot=before)
    finally:
        (tmp_path / "locked.txt").chmod(0o600)

    request = seen[0].event_data
    assert "deleted file" not in request
    assert (
        "could not read these files, so they are not diffed:\n- locked.txt" in request
    )
