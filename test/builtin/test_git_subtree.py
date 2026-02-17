from unittest import mock
import pytest
from zrb.builtin import git_subtree as git_subtree_module
from zrb.util.git_subtree_model import SingleSubTreeConfig, SubTreeConfig
from zrb.session.session import Session
from zrb.context.shared_context import SharedContext
from zrb.task.base.context import fill_shared_context_inputs


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
    with mock.patch("zrb.builtin.git.add", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())) as mock_add, \
         mock.patch("zrb.builtin.git.commit", new=mock.MagicMock(side_effect=lambda *a, **k: _coro())) as mock_commit:
        yield mock_add, mock_commit


# --- Tests for git_add_subtree ---


@pytest.mark.asyncio
async def test_git_add_subtree_success(session, mock_print, mock_git_commit_upstream):
    """Test git_add_subtree calls add_subtree with correct arguments."""
    subtree_name = "libs"
    repo_url = "git@github.com:user/libs.git"
    repo_branch = "main"
    repo_prefix = "src/libs"
    mock_add, mock_commit = mock_git_commit_upstream

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.MagicMock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.add_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_add_subtree:

        # Get the task object
        add_subtree_task = git_subtree_module.git_add_subtree
        fill_shared_context_inputs(
            session.shared_ctx,
            add_subtree_task,
            kwargs={
                "name": subtree_name,
                "repo-url": repo_url,
                "repo-branch": repo_branch,
                "repo-prefix": repo_prefix
            }
        )

        await add_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        mock_add_subtree.assert_called_once()
        call_args = mock_add_subtree.call_args[1]
        assert call_args["repo_dir"] == "/fake/repo"
        assert call_args["name"] == subtree_name
        assert call_args["repo_url"] == repo_url
        assert call_args["branch"] == repo_branch
        assert call_args["prefix"] == repo_prefix


# --- Tests for git_pull_subtree ---


@pytest.mark.asyncio
async def test_git_pull_subtree_success(session, mock_print, mock_git_commit_upstream):
    """Test git_pull_subtree calls pull_subtree for each configured subtree."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
        "libB": SingleSubTreeConfig(
            prefix="src/libB", repo_url="urlB", branch="develop"
        ),
    }
    subtree_config = SubTreeConfig(data=config_data)
    mock_add, mock_commit = mock_git_commit_upstream

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.pull_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_pull_subtree:

        # Get the task object
        pull_subtree_task = git_subtree_module.git_pull_subtree

        await pull_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        mock_load_config.assert_any_call("/fake/repo")
        assert mock_pull_subtree.call_count >= 2
        mock_pull_subtree.assert_any_call(
            repo_dir="/fake/repo",
            prefix="src/libA",
            repo_url="urlA",
            branch="main",
            print_method=mock.ANY,
        )
        mock_pull_subtree.assert_any_call(
            repo_dir="/fake/repo",
            prefix="src/libB",
            repo_url="urlB",
            branch="develop",
            print_method=mock.ANY,
        )


@pytest.mark.asyncio
async def test_git_pull_subtree_no_config(session, mock_print, mock_git_commit_upstream):
    """Test git_pull_subtree raises error if no config is found."""
    subtree_config = SubTreeConfig(data={})
    mock_add, mock_commit = mock_git_commit_upstream

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.pull_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_pull_subtree:

        # Get the task object
        pull_subtree_task = git_subtree_module.git_pull_subtree

        with pytest.raises(ValueError, match="No subtree config found"):
            await pull_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        mock_load_config.assert_any_call("/fake/repo")
        mock_pull_subtree.assert_not_called()


@pytest.mark.asyncio
async def test_git_pull_subtree_handles_error(session, mock_print, mock_git_commit_upstream):
    """Test git_pull_subtree logs errors and raises the first one encountered."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
    }
    subtree_config = SubTreeConfig(data=config_data)
    mock_add, mock_commit = mock_git_commit_upstream

    async def _fail(*a, **k):
        raise Exception("Pull failed")

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ), mock.patch(
        "zrb.builtin.git_subtree.pull_subtree", new=mock.Mock(side_effect=_fail)
    ) as mock_pull_subtree:

        # Get the task object
        pull_subtree_task = git_subtree_module.git_pull_subtree

        with pytest.raises(Exception, match="Pull failed"):
            await pull_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        assert mock_pull_subtree.called


# --- Tests for git_push_subtree ---


@pytest.mark.asyncio
async def test_git_push_subtree_success(session, mock_print, mock_git_commit_upstream):
    """Test git_push_subtree calls push_subtree for each configured subtree."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
        "libB": SingleSubTreeConfig(
            prefix="src/libB", repo_url="urlB", branch="develop"
        ),
    }
    subtree_config = SubTreeConfig(data=config_data)
    mock_add, mock_commit = mock_git_commit_upstream

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.push_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_push_subtree:

        # Get the task object
        push_subtree_task = git_subtree_module.git_push_subtree

        await push_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        mock_load_config.assert_any_call("/fake/repo")
        assert mock_push_subtree.call_count >= 2
        mock_push_subtree.assert_any_call(
            repo_dir="/fake/repo",
            prefix="src/libA",
            repo_url="urlA",
            branch="main",
            print_method=mock.ANY,
        )
        mock_push_subtree.assert_any_call(
            repo_dir="/fake/repo",
            prefix="src/libB",
            repo_url="urlB",
            branch="develop",
            print_method=mock.ANY,
        )


@pytest.mark.asyncio
async def test_git_push_subtree_no_config(session, mock_print, mock_git_commit_upstream):
    """Test git_push_subtree raises error if no config is found."""
    subtree_config = SubTreeConfig(data={})
    mock_add, mock_commit = mock_git_commit_upstream

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.push_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_push_subtree:

        # Get the task object
        push_subtree_task = git_subtree_module.git_push_subtree

        with pytest.raises(ValueError, match="No subtree config found"):
            await push_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        mock_load_config.assert_any_call("/fake/repo")
        mock_push_subtree.assert_not_called()


@pytest.mark.asyncio
async def test_git_push_subtree_handles_error(session, mock_print, mock_git_commit_upstream):
    """Test git_push_subtree logs errors and raises the first one encountered."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
    }
    subtree_config = SubTreeConfig(data=config_data)
    mock_add, mock_commit = mock_git_commit_upstream

    async def _fail(*a, **k):
        raise Exception("Push failed")

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro("/fake/repo")),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ), mock.patch(
        "zrb.builtin.git_subtree.push_subtree", new=mock.Mock(side_effect=_fail)
    ) as mock_push_subtree:

        # Get the task object
        push_subtree_task = git_subtree_module.git_push_subtree

        with pytest.raises(Exception, match="Push failed"):
            await push_subtree_task.async_run(session=session)

        # Ensure upstream git_commit was called
        mock_add.assert_called_once()
        mock_commit.assert_called_once()

        assert mock_push_subtree.called