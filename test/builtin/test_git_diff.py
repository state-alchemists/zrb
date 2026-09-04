from unittest import mock

import pytest

from zrb.builtin import git as git_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.util.git.diff_model import DiffResult


async def _coro(val=None):
    return val


@pytest.fixture
def mock_print():
    return mock.MagicMock()


@pytest.fixture
def session(mock_print):
    shared_ctx = SharedContext(print_fn=mock_print)
    return Session(shared_ctx=shared_ctx, state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_get_git_diff_all_types(session, mock_print):
    """Test get_git_diff includes all file types by default."""
    diff_result = DiffResult(
        created=["new.txt"], updated=["modified.py"], removed=["old.log"]
    )

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_diff",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
        ) as mock_get_diff,
    ):

        # Get the task object
        get_diff_task = git_module.get_git_diff

        result = await get_diff_task.async_run(
            session=session,
            kwargs={
                "source": "main",
                "current": "HEAD",
                "created": True,
                "removed": True,
                "updated": True,
            },
        )

        mock_get_diff.assert_called_with(
            "/fake/repo", "main", "HEAD", print_method=mock.ANY
        )
        assert "new.txt" in result
        assert "modified.py" in result
        assert "old.log" in result


@pytest.mark.asyncio
async def test_get_git_diff_only_created(session, mock_print):
    """Test get_git_diff includes only created files when specified."""
    diff_result = DiffResult(
        created=["new.txt"], updated=["modified.py"], removed=["old.log"]
    )

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_diff",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
        ) as mock_get_diff,
    ):

        # Get the task object
        get_diff_task = git_module.get_git_diff

        result = await get_diff_task.async_run(
            session=session,
            kwargs={
                "source": "main",
                "current": "HEAD",
                "created": True,
                "removed": False,
                "updated": False,
            },
        )

        mock_get_diff.assert_called_with(
            "/fake/repo", "main", "HEAD", print_method=mock.ANY
        )
        assert result == "new.txt"
        assert "modified.py" not in result
        assert "old.log" not in result


@pytest.mark.asyncio
async def test_get_git_diff_no_changes(session, mock_print):
    """Test get_git_diff when there are no changes."""
    diff_result = DiffResult(created=[], updated=[], removed=[])

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_diff",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
        ) as mock_get_diff,
    ):

        # Get the task object
        get_diff_task = git_module.get_git_diff

        result = await get_diff_task.async_run(
            session=session,
            kwargs={
                "source": "main",
                "current": "HEAD",
                "created": True,
                "removed": True,
                "updated": True,
            },
        )

        mock_get_diff.assert_called_with(
            "/fake/repo", "main", "HEAD", print_method=mock.ANY
        )
        assert result == ""


@pytest.mark.asyncio
async def test_prune_local_branches_deletes_merged_non_protected(session, mock_print):
    """Test prune_local_branches deletes merged branches other than main/master/current."""
    branches = ["main", "master", "current-branch", "feature-a", "fix-b"]
    current_branch = "current-branch"

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_branches",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branches)),
        ) as mock_get_branches,
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(current_branch)),
        ) as mock_get_current_branch,
        mock.patch(
            "zrb.builtin.git.is_branch_merged",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(True)),
        ) as mock_is_branch_merged,
        mock.patch(
            "zrb.builtin.git.delete_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_delete_branch,
    ):

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task.async_run(
            session=session, kwargs={"preserved_branch": "master,main,dev,develop"}
        )

        mock_get_branches.assert_called_with("/fake/repo", print_method=mock.ANY)
        mock_get_current_branch.assert_called_with("/fake/repo", print_method=mock.ANY)

        # Check that is_branch_merged was called for 'feature-a' and 'fix-b'
        mock_is_branch_merged.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock.ANY
        )
        mock_is_branch_merged.assert_any_call(
            "/fake/repo", "fix-b", print_method=mock.ANY
        )

        # Check that delete_branch was called for 'feature-a' and 'fix-b'
        mock_delete_branch.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock.ANY
        )
        mock_delete_branch.assert_any_call("/fake/repo", "fix-b", print_method=mock.ANY)


@pytest.mark.asyncio
async def test_prune_local_branches_skips_non_merged(session, mock_print):
    """Test prune_local_branches skips branches not merged to HEAD."""
    branches = ["main", "feature-a", "feature-b"]
    current_branch = "main"

    async def _is_merged_side_effect(repo_dir, branch_name, **kwargs):
        # feature-a is merged, feature-b is not
        return branch_name == "feature-a"

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_branches",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branches)),
        ),
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(current_branch)),
        ),
        mock.patch(
            "zrb.builtin.git.is_branch_merged",
            new=mock.MagicMock(side_effect=_is_merged_side_effect),
        ) as mock_is_branch_merged,
        mock.patch(
            "zrb.builtin.git.delete_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_delete_branch,
    ):

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task.async_run(
            session=session, kwargs={"preserved_branch": "master,main,dev,develop"}
        )

        # Check that delete_branch was called only for 'feature-a' (merged)
        mock_delete_branch.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock.ANY
        )
        # delete_branch should NOT be called for 'feature-b' (not merged)
        mock_delete_branch.assert_called_once()


@pytest.mark.asyncio
async def test_prune_local_branches_handles_delete_error(session, mock_print):
    """Test prune_local_branches logs error if deletion fails."""
    branches = ["main", "feature-a"]
    current_branch = "main"

    async def _fail(*a, **k):
        raise Exception("Deletion failed")

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_branches",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branches)),
        ),
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(current_branch)),
        ),
        mock.patch(
            "zrb.builtin.git.is_branch_merged",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(True)),
        ),
        mock.patch(
            "zrb.builtin.git.delete_branch", new=mock.MagicMock(side_effect=_fail)
        ) as mock_delete_branch,
    ):

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task.async_run(
            session=session, kwargs={"preserved_branch": "master,main,dev,develop"}
        )

        mock_delete_branch.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock.ANY
        )
