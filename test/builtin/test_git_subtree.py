from unittest import mock

import pytest

# Import task objects from the module
from zrb.builtin import git_subtree as git_subtree_module
from zrb.util.git_subtree import SingleSubTreeConfig, SubTreeConfig


@pytest.fixture
def mock_context():
    """Fixture for a mocked AnyContext."""
    context = mock.Mock()
    # Use MagicMock for input to support both attribute and item access easily
    context.input = mock.MagicMock()
    context.print = mock.Mock()
    context.log_error = mock.Mock()
    return context


# --- Tests for git_add_subtree ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.add_subtree")
async def test_git_add_subtree_success(
    mock_add_subtree, mock_get_repo_dir, mock_context
):
    """Test git_add_subtree calls add_subtree with correct arguments."""
    subtree_name = "libs"
    repo_url = "git@github.com:user/libs.git"
    repo_branch = "main"
    repo_prefix = "src/libs"

    # Set values on the input mock
    mock_context.input.name = subtree_name
    # Configure __getitem__ for dictionary-style access

    def getitem_side_effect(key):
        if key == "repo-url":
            return repo_url
        if key == "repo-branch":
            return repo_branch
        if key == "repo-prefix":
            return repo_prefix
        raise KeyError(key)

    mock_context.input.__getitem__.side_effect = getitem_side_effect

    # Get the task object
    add_subtree_task = git_subtree_module.git_add_subtree

    await add_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_add_subtree.assert_called_once_with(
        repo_dir="/fake/repo",
        name=subtree_name,
        repo_url=repo_url,
        branch=repo_branch,
        prefix=repo_prefix,
        print_method=mock_context.print,
    )
    # Check print calls for status updates
    assert mock_context.print.call_count == 2


# --- Tests for git_pull_subtree ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.load_config")
@mock.patch("zrb.builtin.git_subtree.pull_subtree")
async def test_git_pull_subtree_success(
    mock_pull_subtree, mock_load_config, mock_get_repo_dir, mock_context
):
    """Test git_pull_subtree calls pull_subtree for each configured subtree."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
        "libB": SingleSubTreeConfig(
            prefix="src/libB", repo_url="urlB", branch="develop"
        ),
    }
    mock_load_config.return_value = SubTreeConfig(data=config_data)

    # Get the task object
    pull_subtree_task = git_subtree_module.git_pull_subtree

    await pull_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_load_config.assert_called_once_with("/fake/repo")
    assert mock_pull_subtree.call_count == 2
    mock_pull_subtree.assert_any_call(
        repo_dir="/fake/repo",
        prefix="src/libA",
        repo_url="urlA",
        branch="main",
        print_method=mock_context.print,
    )
    mock_pull_subtree.assert_any_call(
        repo_dir="/fake/repo",
        prefix="src/libB",
        repo_url="urlB",
        branch="develop",
        print_method=mock_context.print,
    )
    # Check print calls for status updates (repo_dir + each subtree)
    assert mock_context.print.call_count == 3


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.load_config")
@mock.patch("zrb.builtin.git_subtree.pull_subtree")
async def test_git_pull_subtree_no_config(
    mock_pull_subtree, mock_load_config, mock_get_repo_dir, mock_context
):
    """Test git_pull_subtree raises error if no config is found."""
    mock_load_config.return_value = SubTreeConfig(data={})

    # Get the task object
    pull_subtree_task = git_subtree_module.git_pull_subtree

    with pytest.raises(ValueError, match="No subtree config found"):
        await pull_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_load_config.assert_called_once_with("/fake/repo")
    mock_pull_subtree.assert_not_called()


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.load_config")
@mock.patch(
    "zrb.builtin.git_subtree.pull_subtree", side_effect=Exception("Pull failed")
)
async def test_git_pull_subtree_handles_error(
    mock_pull_subtree, mock_load_config, mock_get_repo_dir, mock_context
):
    """Test git_pull_subtree logs errors and raises the first one encountered."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
    }
    mock_load_config.return_value = SubTreeConfig(data=config_data)

    # Get the task object
    pull_subtree_task = git_subtree_module.git_pull_subtree

    with pytest.raises(Exception, match="Pull failed"):
        await pull_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_load_config.assert_called_once_with("/fake/repo")
    mock_pull_subtree.assert_called_once()  # Called once before failing
    mock_context.log_error.assert_called_once()  # Error should be logged


# --- Tests for git_push_subtree ---


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.load_config")
@mock.patch("zrb.builtin.git_subtree.push_subtree")
async def test_git_push_subtree_success(
    mock_push_subtree, mock_load_config, mock_get_repo_dir, mock_context
):
    """Test git_push_subtree calls push_subtree for each configured subtree."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
        "libB": SingleSubTreeConfig(
            prefix="src/libB", repo_url="urlB", branch="develop"
        ),
    }
    mock_load_config.return_value = SubTreeConfig(data=config_data)

    # Get the task object
    push_subtree_task = git_subtree_module.git_push_subtree

    await push_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_load_config.assert_called_once_with("/fake/repo")
    assert mock_push_subtree.call_count == 2
    mock_push_subtree.assert_any_call(
        repo_dir="/fake/repo",
        prefix="src/libA",
        repo_url="urlA",
        branch="main",
        print_method=mock_context.print,
    )
    mock_push_subtree.assert_any_call(
        repo_dir="/fake/repo",
        prefix="src/libB",
        repo_url="urlB",
        branch="develop",
        print_method=mock_context.print,
    )
    # Check print calls for status updates (repo_dir + each subtree)
    assert mock_context.print.call_count == 3


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.load_config")
@mock.patch("zrb.builtin.git_subtree.push_subtree")
async def test_git_push_subtree_no_config(
    mock_push_subtree, mock_load_config, mock_get_repo_dir, mock_context
):
    """Test git_push_subtree raises error if no config is found."""
    mock_load_config.return_value = SubTreeConfig(data={})

    # Get the task object
    push_subtree_task = git_subtree_module.git_push_subtree

    with pytest.raises(ValueError, match="No subtree config found"):
        await push_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_load_config.assert_called_once_with("/fake/repo")
    mock_push_subtree.assert_not_called()


@pytest.mark.asyncio
@mock.patch("zrb.builtin.git_subtree.get_repo_dir", return_value="/fake/repo")
@mock.patch("zrb.builtin.git_subtree.load_config")
@mock.patch(
    "zrb.builtin.git_subtree.push_subtree", side_effect=Exception("Push failed")
)
async def test_git_push_subtree_handles_error(
    mock_push_subtree, mock_load_config, mock_get_repo_dir, mock_context
):
    """Test git_push_subtree logs errors and raises the first one encountered."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
    }
    mock_load_config.return_value = SubTreeConfig(data=config_data)

    # Get the task object
    push_subtree_task = git_subtree_module.git_push_subtree

    with pytest.raises(Exception, match="Push failed"):
        await push_subtree_task._exec_action(mock_context)

    mock_get_repo_dir.assert_called_once_with(print_method=mock_context.print)
    mock_load_config.assert_called_once_with("/fake/repo")
    mock_push_subtree.assert_called_once()  # Called once before failing
    mock_context.log_error.assert_called_once()  # Error should be logged
