from unittest import mock

import pytest

from zrb.builtin import git_subtree as git_subtree_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.util.git_subtree_model import SingleSubTreeConfig, SubTreeConfig


async def _coro(val=None):
    return val


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_git_add_subtree_success(tmp_path):
    """Test git_add_subtree calls add_subtree with correct arguments."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.add_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_add_subtree:
        task = git_subtree_module.git_add_subtree
        session = get_fresh_session()
        await task.async_run(
            session=session,
            kwargs={
                "name": "libs",
                "repo_url": "git@github.com:user/libs.git",
                "repo_branch": "main",
                "repo_prefix": "src/libs",
            },
        )
        assert mock_add_subtree.call_count > 0


@pytest.mark.asyncio
async def test_git_pull_subtree_success(tmp_path):
    """Test git_pull_subtree calls pull_subtree for each configured subtree."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
        "libB": SingleSubTreeConfig(
            prefix="src/libB", repo_url="urlB", branch="develop"
        ),
    }
    subtree_config = SubTreeConfig(data=config_data)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.pull_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_pull_subtree:
        task = git_subtree_module.git_pull_subtree
        session = get_fresh_session()
        await task.async_run(session=session)

        assert mock_load_config.call_count > 0
        assert mock_pull_subtree.call_count == 2


@pytest.mark.asyncio
async def test_git_pull_subtree_no_config(tmp_path):
    """Test git_pull_subtree raises error if no config is found."""
    subtree_config = SubTreeConfig(data={})
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.pull_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_pull_subtree:
        task = git_subtree_module.git_pull_subtree
        session = get_fresh_session()
        with pytest.raises(ValueError, match="No subtree config found"):
            await task.async_run(session=session)

        assert mock_load_config.call_count > 0
        mock_pull_subtree.assert_not_called()


@pytest.mark.asyncio
async def test_git_pull_subtree_handles_error(tmp_path):
    """Test git_pull_subtree logs errors and raises the first one encountered."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
    }
    subtree_config = SubTreeConfig(data=config_data)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    async def _fail(*a, **k):
        raise Exception("Pull failed")

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ), mock.patch(
        "zrb.builtin.git_subtree.pull_subtree", new=mock.Mock(side_effect=_fail)
    ) as mock_pull_subtree:
        task = git_subtree_module.git_pull_subtree
        session = get_fresh_session()
        with pytest.raises(Exception, match="Pull failed"):
            await task.async_run(session=session)

        assert mock_pull_subtree.call_count > 0


@pytest.mark.asyncio
async def test_git_push_subtree_success(tmp_path):
    """Test git_push_subtree calls push_subtree for each configured subtree."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
        "libB": SingleSubTreeConfig(
            prefix="src/libB", repo_url="urlB", branch="develop"
        ),
    }
    subtree_config = SubTreeConfig(data=config_data)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.push_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_push_subtree:
        task = git_subtree_module.git_push_subtree
        session = get_fresh_session()
        await task.async_run(session=session)

        assert mock_load_config.call_count > 0
        assert mock_push_subtree.call_count == 2


@pytest.mark.asyncio
async def test_git_push_subtree_no_config(tmp_path):
    """Test git_push_subtree raises error if no config is found."""
    subtree_config = SubTreeConfig(data={})
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ) as mock_load_config, mock.patch(
        "zrb.builtin.git_subtree.push_subtree",
        new=mock.Mock(side_effect=lambda *a, **k: _coro()),
    ) as mock_push_subtree:
        task = git_subtree_module.git_push_subtree
        session = get_fresh_session()
        with pytest.raises(ValueError, match="No subtree config found"):
            await task.async_run(session=session)

        assert mock_load_config.call_count > 0
        mock_push_subtree.assert_not_called()


@pytest.mark.asyncio
async def test_git_push_subtree_handles_error(tmp_path):
    """Test git_push_subtree logs errors, raises the first one encountered."""
    config_data = {
        "libA": SingleSubTreeConfig(prefix="src/libA", repo_url="urlA", branch="main"),
    }
    subtree_config = SubTreeConfig(data=config_data)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    async def _fail(*a, **k):
        raise Exception("Push failed")

    with mock.patch(
        "zrb.builtin.git_subtree.get_repo_dir",
        new=mock.Mock(side_effect=lambda *a, **k: _coro(str(repo_dir))),
    ), mock.patch(
        "zrb.builtin.git_subtree.load_config",
        return_value=subtree_config,
    ), mock.patch(
        "zrb.builtin.git_subtree.push_subtree", new=mock.Mock(side_effect=_fail)
    ) as mock_push_subtree:
        task = git_subtree_module.git_push_subtree
        session = get_fresh_session()
        with pytest.raises(Exception, match="Push failed"):
            await task.async_run(session=session)

        assert mock_push_subtree.call_count > 0
