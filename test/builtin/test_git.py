from types import SimpleNamespace
from unittest import mock

import pytest

# Import task objects from the module
from zrb.builtin import git as git_module
from zrb.util.git_diff_model import DiffResult


@pytest.fixture
def mock_context():
    """Fixture for a mocked AnyContext."""
    context = mock.Mock()
    context.input = SimpleNamespace()
    context.print = mock.Mock()
    context.log_error = mock.Mock()
    return context


# --- Tests for get_git_diff ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_diff")
async def test_get_git_diff_all_types(mock_get_diff, mock_get_repo_dir, mock_context):
    """Test get_git_diff includes all file types by default."""
    mock_context.input.source = "main"
    mock_context.input.current = "HEAD"
    mock_context.input.created = True
    mock_context.input.removed = True
    mock_context.input.updated = True

    mock_get_diff.return_value = DiffResult(
        created=["new.txt"], updated=["modified.py"], removed=["old.log"]
    )

    # Get the task object
    get_diff_task = git_module.get_git_diff

    result = await get_diff_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_diff.assert_called_once_with(
        "/fake/repo", "main", "HEAD", print_method=mock_context.print
    )
    assert "new.txt" in result
    assert "modified.py" in result
    assert "old.log" in result
    # Check if print was called for status and results
    assert mock_context.print.call_count >= 2


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_diff")
async def test_get_git_diff_only_created(
    mock_get_diff, mock_get_repo_dir, mock_context
):
    """Test get_git_diff includes only created files when specified."""
    mock_context.input.source = "main"
    mock_context.input.current = "HEAD"
    mock_context.input.created = True
    mock_context.input.removed = False
    mock_context.input.updated = False

    mock_get_diff.return_value = DiffResult(
        created=["new.txt"], updated=["modified.py"], removed=["old.log"]
    )

    # Get the task object
    get_diff_task = git_module.get_git_diff

    result = await get_diff_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_diff.assert_called_once_with(
        "/fake/repo", "main", "HEAD", print_method=mock_context.print
    )
    assert result == "new.txt"
    assert "modified.py" not in result
    assert "old.log" not in result
    assert mock_context.print.call_count >= 2


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_diff")
async def test_get_git_diff_no_changes(mock_get_diff, mock_get_repo_dir, mock_context):
    """Test get_git_diff when there are no changes."""
    mock_context.input.source = "main"
    mock_context.input.current = "HEAD"
    mock_context.input.created = True
    mock_context.input.removed = True
    mock_context.input.updated = True

    mock_get_diff.return_value = DiffResult(created=[], updated=[], removed=[])

    # Get the task object
    get_diff_task = git_module.get_git_diff

    result = await get_diff_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_diff.assert_called_once_with(
        "/fake/repo", "main", "HEAD", print_method=mock_context.print
    )
    assert result == ""
    # Print called for status, but not for empty results list
    assert mock_context.print.call_count == 2


# --- Tests for prune_local_branches ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_branches")
@mock.patch("zrb.builtin.git.get_current_branch")
@mock.patch("zrb.builtin.git.delete_branch")
async def test_prune_local_branches_deletes_non_protected(
    mock_delete_branch,
    mock_get_current_branch,
    mock_get_branches,
    mock_get_repo_dir,
    mock_context,
):
    """Test prune_local_branches deletes branches other than main/master/current."""
    mock_get_branches.return_value = [
        "main",
        "master",
        "current-branch",
        "feature-a",
        "fix-b",
    ]
    mock_get_current_branch.return_value = "current-branch"
    mock_context.input.preserved_branch = "master,main,dev,develop"

    # Get the task object
    prune_task = git_module.prune_local_branches

    await prune_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
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

    # Check that delete_branch was NOT called for protected branches
    protected_calls = [
        mock.call("/fake/repo", "main", print_method=mock_context.print),
        mock.call("/fake/repo", "master", print_method=mock_context.print),
        mock.call("/fake/repo", "current-branch", print_method=mock_context.print),
    ]
    for call in protected_calls:
        assert call not in mock_delete_branch.call_args_list


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_branches")
@mock.patch("zrb.builtin.git.get_current_branch")
@mock.patch("zrb.builtin.git.delete_branch", side_effect=Exception("Deletion failed"))
async def test_prune_local_branches_handles_delete_error(
    mock_delete_branch,
    mock_get_current_branch,
    mock_get_branches,
    mock_get_repo_dir,
    mock_context,
):
    """Test prune_local_branches logs error if deletion fails."""
    mock_get_branches.return_value = ["main", "feature-a"]
    mock_get_current_branch.return_value = "main"
    mock_context.input.preserved_branch = "master,main,dev,develop"

    # Get the task object
    prune_task = git_module.prune_local_branches

    await prune_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_branches.assert_called_once_with(
        "/fake/repo", print_method=mock_context.print
    )
    mock_get_current_branch.assert_called_once_with(
        "/fake/repo", print_method=mock_context.print
    )
    mock_delete_branch.assert_called_once_with(
        "/fake/repo", "feature-a", print_method=mock_context.print
    )
    mock_context.log_error.assert_called_once()  # Check if error was logged


# Tests for git_commit, git_pull, git_push will follow
# --- Tests for git_commit ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.add")
@mock.patch("zrb.builtin.git.commit")
async def test_git_commit_success(
    mock_commit, mock_add, mock_get_repo_dir, mock_context
):
    """Test git_commit calls add and commit with the correct message."""
    commit_message = "Test commit message"
    mock_context.input.message = commit_message

    # Get the task object
    commit_task = git_module.git_commit

    await commit_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_add.assert_called_once_with("/fake/repo", print_method=mock_context.print)
    mock_commit.assert_called_once_with(
        "/fake/repo", commit_message, print_method=mock_context.print
    )
    # Check print calls for status updates
    assert mock_context.print.call_count == 3


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.add", side_effect=Exception("Add failed"))
@mock.patch("zrb.builtin.git.commit")
async def test_git_commit_add_fails(
    mock_commit, mock_add, mock_get_repo_dir, mock_context
):
    """Test git_commit handles failure during the add operation."""
    mock_context.input.message = "Test commit"

    # Get the task object
    commit_task = git_module.git_commit

    with pytest.raises(Exception, match="Add failed"):
        await commit_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_add.assert_called_once_with("/fake/repo", print_method=mock_context.print)
    mock_commit.assert_not_called()  # Commit should not be called if add fails


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.add")
@mock.patch("zrb.builtin.git.commit", side_effect=Exception("Commit failed"))
async def test_git_commit_commit_fails(
    mock_commit, mock_add, mock_get_repo_dir, mock_context
):
    """Test git_commit handles failure during the commit operation."""
    commit_message = "Test commit"
    mock_context.input.message = commit_message

    # Get the task object
    commit_task = git_module.git_commit

    with pytest.raises(Exception, match="Commit failed"):
        await commit_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_add.assert_called_once_with("/fake/repo", print_method=mock_context.print)
    mock_commit.assert_called_once_with(
        "/fake/repo", commit_message, print_method=mock_context.print
    )


# Tests for git_pull, git_push will follow
# --- Tests for git_pull ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_current_branch")
@mock.patch("zrb.builtin.git.pull")
async def test_git_pull_success(
    mock_pull, mock_get_current_branch, mock_get_repo_dir, mock_context
):
    """Test git_pull calls pull with correct remote and branch."""
    remote_name = "origin"
    branch_name = "main"
    mock_context.input.remote = remote_name
    mock_get_current_branch.return_value = branch_name

    # Get the task object
    pull_task = git_module.git_pull

    await pull_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_current_branch.assert_called_once_with(
        "/fake/repo", print_method=mock_context.print
    )
    mock_pull.assert_called_once_with(
        "/fake/repo", remote_name, branch_name, print_method=mock_context.print
    )
    # Check print calls for status updates
    assert mock_context.print.call_count == 3


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_current_branch")
@mock.patch("zrb.builtin.git.pull", side_effect=Exception("Pull failed"))
async def test_git_pull_fails(
    mock_pull, mock_get_current_branch, mock_get_repo_dir, mock_context
):
    """Test git_pull handles failure during the pull operation."""
    remote_name = "upstream"
    branch_name = "develop"
    mock_context.input.remote = remote_name
    mock_get_current_branch.return_value = branch_name

    # Get the task object
    pull_task = git_module.git_pull

    with pytest.raises(Exception, match="Pull failed"):
        await pull_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_current_branch.assert_called_once_with(
        "/fake/repo", print_method=mock_context.print
    )
    mock_pull.assert_called_once_with(
        "/fake/repo", remote_name, branch_name, print_method=mock_context.print
    )


# --- Tests for git_push ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_current_branch")
@mock.patch("zrb.builtin.git.push")
async def test_git_push_success(
    mock_push, mock_get_current_branch, mock_get_repo_dir, mock_context
):
    """Test git_push calls push with correct remote and branch."""
    remote_name = "origin"
    branch_name = "feature/new-thing"
    mock_context.input.remote = remote_name
    mock_get_current_branch.return_value = branch_name

    # Get the task object
    push_task = git_module.git_push

    await push_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_current_branch.assert_called_once_with(
        "/fake/repo", print_method=mock_context.print
    )
    mock_push.assert_called_once_with(
        "/fake/repo", remote_name, branch_name, print_method=mock_context.print
    )
    # Check print calls for status updates
    assert mock_context.print.call_count == 2  # repo_dir is not printed in push


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git.get_current_branch")
@mock.patch("zrb.builtin.git.push", side_effect=Exception("Push failed"))
async def test_git_push_fails(
    mock_push, mock_get_current_branch, mock_get_repo_dir, mock_context
):
    """Test git_push handles failure during the push operation."""
    remote_name = "backup"
    branch_name = "release/v1.0"
    mock_context.input.remote = remote_name
    mock_get_current_branch.return_value = branch_name

    # Get the task object
    push_task = git_module.git_push

    with pytest.raises(Exception, match="Push failed"):
        await push_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once()
    mock_get_current_branch.assert_called_once_with(
        "/fake/repo", print_method=mock_context.print
    )
    mock_push.assert_called_once_with(
        "/fake/repo", remote_name, branch_name, print_method=mock_context.print
    )
