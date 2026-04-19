import asyncio
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.prompt.system_context import system_context
from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees


@pytest.fixture
def mock_subprocess():
    with patch("asyncio.create_subprocess_exec") as mock:
        yield mock


def create_mock_process(returncode=0, stdout=b"", stderr=b""):
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    return process


@pytest.mark.asyncio
async def test_enter_worktree_success(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(
            returncode=0, stdout=b"Preparing worktree", stderr=b""
        ),  # git worktree add
    ]

    res = await enter_worktree(branch_name="test-branch")
    assert "Worktree created:" in res
    assert "Branch: test-branch" in res


@pytest.mark.asyncio
async def test_enter_worktree_no_branch_name(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(returncode=0),  # git worktree add
    ]
    res = await enter_worktree()
    assert "Worktree created:" in res
    assert "Branch: worktree-" in res


@pytest.mark.asyncio
async def test_enter_worktree_not_repo(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=1, stderr=b"fatal: not a git repository"
    )
    res = await enter_worktree()
    assert "Error" in res
    assert "git repository" in res


@pytest.mark.asyncio
async def test_enter_worktree_failure(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(
            returncode=1, stderr=b"fatal: branch already exists"
        ),  # git worktree add
    ]
    res = await enter_worktree(branch_name="existing-branch")
    assert "Error" in res
    assert "already exists" in res


@pytest.mark.asyncio
async def test_exit_worktree_success(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(returncode=0),  # git worktree remove
            create_mock_process(returncode=0),  # git branch -D
        ]
        res = await exit_worktree(tmpdir)
        assert f"Worktree removed: {tmpdir}" in res
        assert "Branch deleted: test-branch" in res


@pytest.mark.asyncio
async def test_exit_worktree_keep_branch(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(returncode=0),  # git worktree remove
        ]
        res = await exit_worktree(tmpdir, keep_branch=True)
        assert f"Worktree removed: {tmpdir}" in res
        assert "Branch kept: test-branch" in res


@pytest.mark.asyncio
async def test_exit_worktree_not_exists():
    res = await exit_worktree("/non/existent/path")
    assert "Error" in res
    assert "does not exist" in res


@pytest.mark.asyncio
async def test_exit_worktree_remove_failure(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(
                returncode=1, stderr=b"error: worktree contains modified files"
            ),  # git worktree remove
        ]
        res = await exit_worktree(tmpdir)
        assert "Error" in res
        assert "modified files" in res


@pytest.mark.asyncio
async def test_exit_worktree_branch_delete_failure(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(returncode=0),  # git worktree remove
            create_mock_process(
                returncode=1, stderr=b"error: branch not found"
            ),  # git branch -D
        ]
        res = await exit_worktree(tmpdir)
        assert f"Worktree removed: {tmpdir}" in res
        assert "could not delete" in res.lower()


@pytest.mark.asyncio
async def test_list_worktrees_success(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=0, stdout=b"/path/to/repo main\n/path/to/worktree branch-name"
    )
    res = await list_worktrees()
    assert "/path/to/repo main" in res
    assert "/path/to/worktree branch-name" in res


@pytest.mark.asyncio
async def test_list_worktrees_empty(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(returncode=0, stdout=b"")
    res = await list_worktrees()
    assert "No worktrees found" in res


@pytest.mark.asyncio
async def test_list_worktrees_failure(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=1, stderr=b"fatal: not a git repository"
    )
    res = await list_worktrees()
    assert "Error" in res
    assert "git repository" in res


def _capture_system_context(ctx=None) -> str:
    """Helper: run system_context and return the enriched prompt."""
    if ctx is None:
        ctx = MagicMock()
        ctx.input.session = "test-session"
    captured = []

    def next_handler(c, p):
        captured.append(p)
        return "ok"

    system_context(ctx, "", next_handler)
    return captured[0]


@pytest.mark.asyncio
async def test_enter_worktree_adds_gitignore_entry(mock_subprocess):
    """EnterWorktree should add the worktree pattern to .gitignore if absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="gi-branch", cwd=tmpdir)

        gitignore = os.path.join(tmpdir, ".gitignore")
        assert os.path.exists(gitignore)
        content = open(gitignore).read()
        assert ".zrb/worktree/" in content


@pytest.mark.asyncio
async def test_enter_worktree_does_not_duplicate_gitignore_entry(mock_subprocess):
    """EnterWorktree should not add a duplicate line if the pattern is already present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore = os.path.join(tmpdir, ".gitignore")
        with open(gitignore, "w") as f:
            f.write(".zrb/worktree/\n")

        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="nodup-branch", cwd=tmpdir)

        content = open(gitignore).read()
        assert content.count(".zrb/worktree/") == 1


@pytest.mark.asyncio
async def test_enter_worktree_appends_to_existing_gitignore(mock_subprocess):
    """EnterWorktree should append to an existing .gitignore without clobbering it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore = os.path.join(tmpdir, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("*.pyc\n__pycache__\n")

        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="append-branch", cwd=tmpdir)

        content = open(gitignore).read()
        assert "*.pyc" in content
        assert "__pycache__" in content
        assert ".zrb/worktree/" in content


@pytest.mark.asyncio
async def test_enter_and_exit_worktree_reflected_in_system_context(mock_subprocess):
    """EnterWorktree shows active worktree in system context; ExitWorktree clears it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree_path = os.path.join(tmpdir, ".zrb", "worktree", "sc-branch")

        # Enter
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="sc-branch", cwd=tmpdir)
        assert "Active worktree:" in _capture_system_context()

        # Exit
        os.makedirs(worktree_path, exist_ok=True)
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=b"sc-branch\n"),
            create_mock_process(returncode=0),
            create_mock_process(returncode=0),
        ]
        await exit_worktree(worktree_path)
        assert "Active worktree:" not in _capture_system_context()
