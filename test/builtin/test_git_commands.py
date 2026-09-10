from unittest import mock

import pytest

from zrb.builtin import git as git_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


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
    with (
        mock.patch(
            "zrb.builtin.git.add",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_add,
        mock.patch(
            "zrb.builtin.git.commit",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_commit,
    ):
        yield mock_add, mock_commit


@pytest.mark.asyncio
async def test_git_commit_success(session, mock_print):
    """Test git_commit calls add and commit with the correct message."""
    commit_message = "Test commit message"

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.add",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_add,
        mock.patch(
            "zrb.builtin.git.commit",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_commit,
    ):

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

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.add", new=mock.MagicMock(side_effect=_fail)
        ) as mock_add,
        mock.patch(
            "zrb.builtin.git.commit",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_commit,
    ):

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

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.add",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_add,
        mock.patch(
            "zrb.builtin.git.commit", new=mock.MagicMock(side_effect=_fail)
        ) as mock_commit,
    ):

        # Get the task object
        commit_task = git_module.git_commit

        with pytest.raises(Exception, match="Commit failed"):
            await commit_task.async_run(
                session=session, kwargs={"message": commit_message}
            )

        mock_add.assert_any_call("/fake/repo", print_method=mock.ANY)
        mock_commit.assert_any_call("/fake/repo", commit_message, print_method=mock.ANY)


@pytest.mark.asyncio
async def test_git_pull_success(session, mock_print, mock_git_commit_upstream):
    """Test git_pull calls pull with correct remote and branch."""
    remote_name = "origin"
    branch_name = "main"
    mock_add, mock_commit = mock_git_commit_upstream

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
        ) as mock_get_current_branch,
        mock.patch(
            "zrb.builtin.git.pull",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_pull,
    ):

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

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
        ),
        mock.patch(
            "zrb.builtin.git.pull", new=mock.MagicMock(side_effect=_fail)
        ) as mock_pull,
    ):

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


@pytest.mark.asyncio
async def test_git_push_success(session, mock_print, mock_git_commit_upstream):
    """Test git_push calls push with correct remote and branch."""
    remote_name = "origin"
    branch_name = "feature/new-thing"
    mock_add, mock_commit = mock_git_commit_upstream

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
        ) as mock_get_current_branch,
        mock.patch(
            "zrb.builtin.git.push",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro()),
        ) as mock_push,
    ):

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

    with (
        mock.patch(
            "zrb.builtin.git.get_repo_dir",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
        ),
        mock.patch(
            "zrb.builtin.git.get_current_branch",
            new=mock.MagicMock(side_effect=lambda *a, **k: _coro(branch_name)),
        ),
        mock.patch(
            "zrb.builtin.git.push", new=mock.MagicMock(side_effect=_fail)
        ) as mock_push,
    ):

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
