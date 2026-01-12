from types import SimpleNamespace
from unittest import mock

import pytest

# Import task objects from the module
from zrb.builtin import git as git_module
from zrb.util.git_diff_model import DiffResult


async def _coro(val=None):
    return val


@pytest.fixture
def mock_context():
    """Fixture for a mocked AnyContext."""
    context = mock.MagicMock()
    context.input = SimpleNamespace()
    context.print = mock.MagicMock()
    context.log_error = mock.MagicMock()
    return context


# --- Tests for get_git_diff ---


@pytest.mark.asyncio
async def test_get_git_diff_all_types(mock_context):
    """Test get_git_diff includes all file types by default."""
    mock_context.input.source = "main"
    mock_context.input.current = "HEAD"
    mock_context.input.created = True
    mock_context.input.removed = True
    mock_context.input.updated = True

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

        # Get the task object
        get_diff_task = git_module.get_git_diff

        result = await get_diff_task._exec_action(mock_context)

        mock_get_diff.assert_called_once_with(
            "/fake/repo", "main", "HEAD", print_method=mock_context.print
        )
        assert "new.txt" in result
        assert "modified.py" in result
        assert "old.log" in result
        # Check if print was called for status and results
        assert mock_context.print.call_count >= 2


@pytest.mark.asyncio
async def test_get_git_diff_only_created(mock_context):
    """Test get_git_diff includes only created files when specified."""
    mock_context.input.source = "main"
    mock_context.input.current = "HEAD"
    mock_context.input.created = True
    mock_context.input.removed = False
    mock_context.input.updated = False

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

        # Get the task object
        get_diff_task = git_module.get_git_diff

        result = await get_diff_task._exec_action(mock_context)

        mock_get_diff.assert_called_once_with(
            "/fake/repo", "main", "HEAD", print_method=mock_context.print
        )
        assert result == "new.txt"
        assert "modified.py" not in result
        assert "old.log" not in result
        assert mock_context.print.call_count >= 2


@pytest.mark.asyncio
async def test_get_git_diff_no_changes(mock_context):
    """Test get_git_diff when there are no changes."""
    mock_context.input.source = "main"
    mock_context.input.current = "HEAD"
    mock_context.input.created = True
    mock_context.input.removed = True
    mock_context.input.updated = True

    diff_result = DiffResult(created=[], updated=[], removed=[])

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_diff",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
    ) as mock_get_diff:

        # Get the task object
        get_diff_task = git_module.get_git_diff

        result = await get_diff_task._exec_action(mock_context)

        mock_get_diff.assert_called_once_with(
            "/fake/repo", "main", "HEAD", print_method=mock_context.print
        )
        assert result == ""
        # Print called for status, but not for empty results list
        assert mock_context.print.call_count == 2


# --- Tests for prune_local_branches ---


@pytest.mark.asyncio
async def test_prune_local_branches_deletes_non_protected(mock_context):
    """Test prune_local_branches deletes branches other than main/master/current."""
    branches = ["main", "master", "current-branch", "feature-a", "fix-b"]
    current_branch = "current-branch"
    mock_context.input.preserved_branch = "master,main,dev,develop"

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

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task._exec_action(mock_context)

        mock_get_branches.assert_called_once_with(
            "/fake/repo", print_method=mock_context.print
        )
        mock_get_current_branch.assert_called_once_with(
            "/fake/repo", print_method=mock_context.print
        )

        # Check that delete_branch was called for 'feature-a' and 'fix-b'
        assert mock_delete_branch.call_count == 2
        mock_delete_branch.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock_context.print
        )
        mock_delete_branch.assert_any_call(
            "/fake/repo", "fix-b", print_method=mock_context.print
        )


@pytest.mark.asyncio
async def test_prune_local_branches_handles_delete_error(mock_context):
    """Test prune_local_branches logs error if deletion fails."""
    branches = ["main", "feature-a"]
    current_branch = "main"
    mock_context.input.preserved_branch = "master,main,dev,develop"

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

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task._exec_action(mock_context)

        mock_delete_branch.assert_called_once_with(
            "/fake/repo", "feature-a", print_method=mock_context.print
        )
        mock_context.log_error.assert_called_once()  # Check if error was logged


# --- Tests for git_commit ---


@pytest.mark.asyncio
async def test_git_commit_success(mock_context):
    """Test git_commit calls add and commit with the correct message."""
    commit_message = "Test commit message"
    mock_context.input.message = commit_message

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.add", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_add, mock.patch(
        "zrb.builtin.git.commit",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
    ) as mock_commit:

        # Get the task object
        commit_task = git_module.git_commit

        await commit_task._exec_action(mock_context)

        mock_add.assert_called_once_with("/fake/repo", print_method=mock_context.print)
        mock_commit.assert_called_once_with(
            "/fake/repo", commit_message, print_method=mock_context.print
        )
        # Check print calls for status updates
        assert mock_context.print.call_count == 3


@pytest.mark.asyncio
async def test_git_commit_add_fails(mock_context):
    """Test git_commit handles failure during the add operation."""
    mock_context.input.message = "Test commit"

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

        # Get the task object
        commit_task = git_module.git_commit

        with pytest.raises(Exception, match="Add failed"):
            await commit_task._exec_action(mock_context)

        mock_add.assert_called_once_with("/fake/repo", print_method=mock_context.print)
        mock_commit.assert_not_called()  # Commit should not be called if add fails


@pytest.mark.asyncio
async def test_git_commit_commit_fails(mock_context):
    """Test git_commit handles failure during the commit operation."""
    commit_message = "Test commit"
    mock_context.input.message = commit_message

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

        # Get the task object
        commit_task = git_module.git_commit

        with pytest.raises(Exception, match="Commit failed"):
            await commit_task._exec_action(mock_context)

        mock_add.assert_called_once_with("/fake/repo", print_method=mock_context.print)
        mock_commit.assert_called_once_with(
            "/fake/repo", commit_message, print_method=mock_context.print
        )


# --- Tests for git_pull ---


@pytest.mark.asyncio
async def test_git_pull_success(mock_context):
    """Test git_pull calls pull with correct remote and branch."""
    remote_name = "origin"
    branch_name = "main"
    mock_context.input.remote = remote_name

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
    ) as mock_get_current_branch, mock.patch(
        "zrb.builtin.git.pull", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_pull:

        # Get the task object
        pull_task = git_module.git_pull

        await pull_task._exec_action(mock_context)

        mock_get_current_branch.assert_called_once_with(
            "/fake/repo", print_method=mock_context.print
        )
        mock_pull.assert_called_once_with(
            "/fake/repo", remote_name, branch_name, print_method=mock_context.print
        )
        # Check print calls for status updates
        assert mock_context.print.call_count == 3


@pytest.mark.asyncio
async def test_git_pull_fails(mock_context):
    """Test git_pull handles failure during the pull operation."""
    remote_name = "upstream"
    branch_name = "develop"
    mock_context.input.remote = remote_name

    async def _fail(*a, **k):
        raise Exception("Pull failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
    ), mock.patch(
        "zrb.builtin.git.pull", new=mock.MagicMock(side_effect=_fail)
    ) as mock_pull:

        # Get the task object
        pull_task = git_module.git_pull

        with pytest.raises(Exception, match="Pull failed"):
            await pull_task._exec_action(mock_context)

        mock_pull.assert_called_once_with(
            "/fake/repo", remote_name, branch_name, print_method=mock_context.print
        )


# --- Tests for git_push ---


@pytest.mark.asyncio
async def test_git_push_success(mock_context):
    """Test git_push calls push with correct remote and branch."""
    remote_name = "origin"
    branch_name = "feature/new-thing"
    mock_context.input.remote = remote_name

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
    ) as mock_get_current_branch, mock.patch(
        "zrb.builtin.git.push", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_push:

        # Get the task object
        push_task = git_module.git_push

        await push_task._exec_action(mock_context)

        mock_get_current_branch.assert_called_once_with(
            "/fake/repo", print_method=mock_context.print
        )
        mock_push.assert_called_once_with(
            "/fake/repo", remote_name, branch_name, print_method=mock_context.print
        )
        # Check print calls for status updates
        assert mock_context.print.call_count == 2  # repo_dir is not printed in push


@pytest.mark.asyncio
async def test_git_push_fails(mock_context):
    """Test git_push handles failure during the push operation."""
    remote_name = "backup"
    branch_name = "release/v1.0"
    mock_context.input.remote = remote_name

    async def _fail(*a, **k):
        raise Exception("Push failed")

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_current_branch",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
    ), mock.patch(
        "zrb.builtin.git.push", new=mock.MagicMock(side_effect=_fail)
    ) as mock_push:

        # Get the task object
        push_task = git_module.git_push

        with pytest.raises(Exception, match="Push failed"):
            await push_task._exec_action(mock_context)

        mock_push.assert_called_once_with(
            "/fake/repo", remote_name, branch_name, print_method=mock_context.print
        )
