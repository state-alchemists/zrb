import asyncio
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    # Mock git rev-parse (check repo)
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(
            returncode=0, stdout=b"Preparing worktree", stderr=b""
        ),  # git worktree add
    ]

    res = await enter_worktree(branch_name="test-branch")
    assert "Worktree created at" in res
    assert "Branch: test-branch" in res


@pytest.mark.asyncio
async def test_enter_worktree_no_branch_name(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(returncode=0),  # git worktree add
    ]
    res = await enter_worktree()
    assert "Worktree created at" in res
    assert "Branch: worktree-" in res


@pytest.mark.asyncio
async def test_enter_worktree_not_repo(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=1, stderr=b"fatal: not a git repository"
    )
    with pytest.raises(RuntimeError, match="Not inside a git repository"):
        await enter_worktree()


@pytest.mark.asyncio
async def test_enter_worktree_failure(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(
            returncode=1, stderr=b"fatal: branch already exists"
        ),  # git worktree add
    ]
    with pytest.raises(
        RuntimeError, match="Failed to create worktree: fatal: branch already exists"
    ):
        await enter_worktree(branch_name="existing-branch")


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
    with pytest.raises(RuntimeError, match="Worktree path does not exist"):
        await exit_worktree("/non/existent/path")


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
        with pytest.raises(
            RuntimeError,
            match="Failed to remove worktree: error: worktree contains modified files",
        ):
            await exit_worktree(tmpdir)


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
        assert "Could not delete branch test-branch: error: branch not found" in res


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
    assert "No additional worktrees found." == res


@pytest.mark.asyncio
async def test_list_worktrees_failure(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=1, stderr=b"fatal: not a git repository"
    )
    with pytest.raises(
        RuntimeError, match="Failed to list worktrees: fatal: not a git repository"
    ):
        await list_worktrees()
