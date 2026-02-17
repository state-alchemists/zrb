from unittest import mock

import pytest

from zrb.builtin import git as git_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.base.context import fill_shared_context_inputs
from zrb.util.git_diff_model import DiffResult


async def _coro(val=None):
    return val


@pytest.fixture
def mock_print():
    return mock.MagicMock()


@pytest.fixture
def session(mock_print):
    shared_ctx = SharedContext(print_fn=mock_print)
    return Session(shared_ctx=shared_ctx, state_logger=mock.MagicMock())


@pytest.fixture
def mock_git_commit_upstream():
    """Mocks the git operations performed by the upstream git-commit task."""
    with mock.patch(
        "zrb.builtin.git.add", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())
    ) as mock_add, mock.patch(
        "zrb.builtin.git.commit",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
    ) as mock_commit:
        yield mock_add, mock_commit


# --- Tests for get_git_diff ---


@pytest.mark.asyncio
async def test_get_git_diff_all_types(session, mock_print):
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

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_diff",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
    ) as mock_get_diff:

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

    with mock.patch(
        "zrb.builtin.git.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git.get_diff",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro(diff_result)),
    ) as mock_get_diff:

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


# --- Tests for prune_local_branches ---


@pytest.mark.asyncio
async def test_prune_local_branches_deletes_non_protected(session, mock_print):
    """Test prune_local_branches deletes branches other than main/master/current."""
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

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task.async_run(
            session=session, kwargs={"preserved_branch": "master,main,dev,develop"}
        )

        mock_get_branches.assert_called_with("/fake/repo", print_method=mock.ANY)
        mock_get_current_branch.assert_called_with("/fake/repo", print_method=mock.ANY)

        # Check that delete_branch was called for 'feature-a' and 'fix-b'
        mock_delete_branch.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock.ANY
        )
        mock_delete_branch.assert_any_call("/fake/repo", "fix-b", print_method=mock.ANY)


@pytest.mark.asyncio
async def test_prune_local_branches_handles_delete_error(session, mock_print):
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

        # Get the task object
        prune_task = git_module.prune_local_branches

        await prune_task.async_run(
            session=session, kwargs={"preserved_branch": "master,main,dev,develop"}
        )

        mock_delete_branch.assert_any_call(
            "/fake/repo", "feature-a", print_method=mock.ANY
        )


# --- Tests for git_commit ---


@pytest.mark.asyncio
async def test_git_commit_success(session, mock_print):
    """Test git_commit calls add and commit with the correct message."""
    commit_message = "Test commit message"

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

        await commit_task.async_run(session=session, kwargs={"message": commit_message})

        mock_add.assert_called_with("/fake/repo", print_method=mock.ANY)
        mock_commit.assert_called_with(
            "/fake/repo", commit_message, print_method=mock.ANY
        )


@pytest.mark.asyncio
async def test_git_commit_add_fails(session, mock_print):
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

        # Get the task object
        commit_task = git_module.git_commit

        with pytest.raises(Exception, match="Add failed"):
            await commit_task.async_run(
                session=session, kwargs={"message": "Test commit"}
            )

        mock_add.assert_any_call("/fake/repo", print_method=mock.ANY)
        mock_commit.assert_not_called()  # Commit should not be called if add fails


@pytest.mark.asyncio
async def test_git_commit_commit_fails(session, mock_print):
    """Test git_commit handles failure during the commit operation."""
    commit_message = "Test commit"

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
            await commit_task.async_run(
                session=session, kwargs={"message": commit_message}
            )

        mock_add.assert_any_call("/fake/repo", print_method=mock.ANY)
        mock_commit.assert_any_call("/fake/repo", commit_message, print_method=mock.ANY)


# --- Tests for git_pull ---


@pytest.mark.asyncio
async def test_git_pull_success(session, mock_print, mock_git_commit_upstream):
    """Test git_pull calls pull with correct remote and branch."""
    remote_name = "origin"
    branch_name = "main"
    mock_add, mock_commit = mock_git_commit_upstream

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

        await pull_task.async_run(session=session, kwargs={"remote": remote_name})

        # Ensure upstream git_commit was called
        assert mock_add.called
        assert mock_commit.called

        # Ensure git_pull actions were called
        mock_get_current_branch.assert_called_with("/fake/repo", print_method=mock.ANY)
        mock_pull.assert_called_with(
            "/fake/repo", remote_name, branch_name, print_method=mock.ANY
        )


@pytest.mark.asyncio
async def test_git_pull_fails(session, mock_print, mock_git_commit_upstream):
    """Test git_pull handles failure during the pull operation."""
    remote_name = "upstream"
    branch_name = "develop"
    mock_add, mock_commit = mock_git_commit_upstream

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
            await pull_task.async_run(session=session, kwargs={"remote": remote_name})

        # Ensure upstream git_commit was called
        assert mock_add.called
        assert mock_commit.called

        mock_pull.assert_any_call(
            "/fake/repo", remote_name, branch_name, print_method=mock.ANY
        )


# --- Tests for git_push ---


@pytest.mark.asyncio
async def test_git_push_success(session, mock_print, mock_git_commit_upstream):
    """Test git_push calls push with correct remote and branch."""
    remote_name = "origin"
    branch_name = "feature/new-thing"
    mock_add, mock_commit = mock_git_commit_upstream

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

        await push_task.async_run(session=session, kwargs={"remote": remote_name})

        # Ensure upstream git_commit was called
        assert mock_add.called
        assert mock_commit.called

        # Ensure git_push actions were called
        mock_get_current_branch.assert_called_with("/fake/repo", print_method=mock.ANY)
        mock_push.assert_called_with(
            "/fake/repo", remote_name, branch_name, print_method=mock.ANY
        )


@pytest.mark.asyncio
async def test_git_push_fails(session, mock_print, mock_git_commit_upstream):
    """Test git_push handles failure during the push operation."""
    remote_name = "backup"
    branch_name = "release/v1.0"
    mock_add, mock_commit = mock_git_commit_upstream

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
            await push_task.async_run(session=session, kwargs={"remote": remote_name})

        # Ensure upstream git_commit was called
        assert mock_add.called
        assert mock_commit.called

        mock_push.assert_any_call(
            "/fake/repo", remote_name, branch_name, print_method=mock.ANY
        )
