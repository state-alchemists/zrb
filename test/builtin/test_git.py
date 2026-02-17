from unittest import mock

import pytest

from zrb.builtin import git as git_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.util.git_diff_model import DiffResult


async def _coro(val=None):
    return val


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_get_git_diff_all_types():
    """Test get_git_diff includes all file types by default."""
    diff_result = DiffResult(
        created=["new.txt"], updated=["modified.py"], removed=["old.log"]
    )
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_diff",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
    ) as mock_get_diff:
        task = git_module.get_git_diff
        session = get_fresh_session()
        session.set_main_task(task)
        await task.async_run(
            session=session,
            kwargs={
                "source": "main",
                "current": "HEAD",
                "created": True,
                "removed": True,
                "updated": True,
            },
        )
        result = session.final_result
        assert "new.txt" in result
        assert "modified.py" in result
        assert "old.log" in result


@pytest.mark.asyncio
async def test_get_git_diff_only_created():
    """Test get_git_diff includes only created files when specified."""
    diff_result = DiffResult(
        created=["new.txt"], updated=["modified.py"], removed=["old.log"]
    )
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_diff",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
    ) as mock_get_diff:
        task = git_module.get_git_diff
        session = get_fresh_session()
        session.set_main_task(task)
        await task.async_run(
            session=session,
            kwargs={
                "source": "main",
                "current": "HEAD",
                "created": True,
                "removed": False,
                "updated": False,
            },
        )
        result = session.final_result
        assert result == "new.txt"
        assert "modified.py" not in result
        assert "old.log" not in result


@pytest.mark.asyncio
async def test_get_git_diff_no_changes():
    """Test get_git_diff when there are no changes."""
    diff_result = DiffResult(created=[], updated=[], removed=[])
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_diff",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
    ) as mock_get_diff:
        task = git_module.get_git_diff
        session = get_fresh_session()
        session.set_main_task(task)
        await task.async_run(
            session=session,
            kwargs={
                "source": "main",
                "current": "HEAD",
                "created": True,
                "removed": True,
                "updated": True,
            },
        )
        result = session.final_result
        assert result == ""


@pytest.mark.asyncio
async def test_prune_local_branches_deletes_non_protected():
    """Test prune_local_branches"""
    branches = ["main", "master", "current-branch", "feature-a", "fix-b"]
    current_branch = "current-branch"
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_branches",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branches)),
    ) as mock_get_branches, mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(current_branch)),
    ) as mock_get_current_branch, mock.patch(
        "zrb.builtin.git.delete_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
    ) as mock_delete_branch:
        task = git_module.prune_local_branches
        session = get_fresh_session()
        await task.async_run(
            session=session,
            kwargs={"preserved_branch": "master,main,dev,develop"},
        )
        assert mock_delete_branch.call_count == 2


@pytest.mark.asyncio
async def test_prune_local_branches_handles_delete_error():
    """Test prune_local_branches logs error if deletion fails."""
    branches = ["main", "feature-a"]
    current_branch = "main"

    async def _fail(*a, **k):
        raise Exception("Deletion failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_branches",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branches)),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(current_branch)),
    ), mock.patch(
        "zrb.builtin.git.delete_branch", new=mock.MagicMock(side_effect=_fail)
    ) as mock_delete_branch:
        task = git_module.prune_local_branches
        session = get_fresh_session()
        await task.async_run(
            session=session,
            kwargs={"preserved_branch": "master,main,dev,develop"},
        )
        assert "Deletion failed" in session.shared_ctx.error_log


@pytest.mark.asyncio
async def test_git_commit_success():
    """Test git_commit calls add and commit with the correct message."""
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.add", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_add, mock.patch(
        "zrb.builtin.git.commit",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
    ) as mock_commit:
        task = git_module.git_commit
        session = get_fresh_session()
        await task.async_run(
            session=session, kwargs={"message": "Test commit message"}
        )
        mock_add.assert_called_once()
        mock_commit.assert_called_once()


@pytest.mark.asyncio
async def test_git_commit_add_fails():
    """Test git_commit handles failure during the add operation."""

    async def _fail(*a, **k):
        raise Exception("Add failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.add", new=mock.MagicMock(side_effect=_fail)
    ) as mock_add, mock.patch(
        "zrb.builtin.git.commit",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
    ) as mock_commit:
        task = git_module.git_commit
        session = get_fresh_session()
        with pytest.raises(Exception, match="Add failed"):
            await task.async_run(session=session, kwargs={"message": "Test commit"})
        mock_add.assert_called_once()
        mock_commit.assert_not_called()


@pytest.mark.asyncio
async def test_git_commit_commit_fails():
    """Test git_commit handles failure during the commit operation."""

    async def _fail(*a, **k):
        raise Exception("Commit failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.add", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_add, mock.patch(
        "zrb.builtin.git.commit", new=mock.MagicMock(side_effect=_fail)
    ) as mock_commit:
        task = git_module.git_commit
        session = get_fresh_session()
        with pytest.raises(Exception, match="Commit failed"):
            await task.async_run(session=session, kwargs={"message": "Test commit"})
        mock_add.assert_called_once()
        mock_commit.assert_called_once()


@pytest.mark.asyncio
async def test_git_pull_success():
    """Test git_pull calls pull with correct remote and branch."""
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("main")),
    ) as mock_get_current_branch, mock.patch(
        "zrb.builtin.git.pull", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_pull:
        task = git_module.git_pull
        session = get_fresh_session()
        await task.async_run(session=session, kwargs={"remote": "origin"})
        mock_get_current_branch.assert_called_once()
        mock_pull.assert_called_once()


@pytest.mark.asyncio
async def test_git_pull_fails():
    """Test git_pull handles failure during the pull operation."""

    async def _fail(*a, **k):
        raise Exception("Pull failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("develop")),
    ), mock.patch(
        "zrb.builtin.git.pull", new=mock.MagicMock(side_effect=_fail)
    ) as mock_pull:
        task = git_module.git_pull
        session = get_fresh_session()
        with pytest.raises(Exception, match="Pull failed"):
            await task.async_run(session=session, kwargs={"remote": "upstream"})
        mock_pull.assert_called_once()


@pytest.mark.asyncio
async def test_git_push_success():
    """Test git_push calls push with correct remote and branch."""
    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("feature/new-thing")),
    ) as mock_get_current_branch, mock.patch(
        "zrb.builtin.git.push", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_push:
        task = git_module.git_push
        session = get_fresh_session()
        await task.async_run(session=session, kwargs={"remote": "origin"})
        mock_get_current_branch.assert_called_once()
        mock_push.assert_called_once()


@pytest.mark.asyncio
async def test_git_push_fails():
    """Test git_push handles failure during the push operation."""

    async def _fail(*a, **k):
        raise Exception("Push failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("release/v1.0")),
    ), mock.patch(
        "zrb.builtin.git.push", new=mock.MagicMock(side_effect=_fail)
    ) as mock_push:
        task = git_module.git_push
        session = get_fresh_session()
        with pytest.raises(Exception, match="Push failed"):
            await task.async_run(session=session, kwargs={"remote": "backup"})
        mock_push.assert_called_once()
