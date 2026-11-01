from unittest import mock

import pytest

from zrb.cmd.command import CmdResult
from zrb.git.subtree import (
    add_subtree,
    load_config,
    pull_subtree,
    push_subtree,
    save_config,
)
from zrb.git.subtree_model import SingleSubTreeConfig, SubTreeConfig


def test_load_config_not_exists(tmp_path):
    config = load_config(str(tmp_path))
    assert isinstance(config, SubTreeConfig)
    assert config.data == {}


def test_save_and_load_config(tmp_path):
    repo_dir = str(tmp_path)
    config = SubTreeConfig(
        data={
            "libA": SingleSubTreeConfig(
                prefix="src/libA", repo_url="urlA", branch="main"
            )
        }
    )
    save_config(repo_dir, config)

    loaded = load_config(repo_dir)
    assert "libA" in loaded.data
    assert loaded.data["libA"].prefix == "src/libA"
    assert loaded.data["libA"].repo_url == "urlA"
    assert loaded.data["libA"].branch == "main"


@pytest.mark.asyncio
async def test_add_subtree_success(tmp_path):
    repo_dir = str(tmp_path)
    # Mock run_command to return success tuple (CmdResult, exit_code)
    # CmdResult args: output, error, display
    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        await add_subtree(
            repo_dir=repo_dir,
            name="libA",
            repo_url="urlA",
            branch="main",
            prefix="src/libA",
        )

    config = load_config(repo_dir)
    assert "libA" in config.data
    assert config.data["libA"].repo_url == "urlA"


@pytest.mark.asyncio
async def test_pull_subtree_success(tmp_path):
    repo_dir = str(tmp_path)
    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        await pull_subtree(repo_dir, "src/libA", "urlA", "main")
        mock_run.assert_called_once()
        assert "pull" in mock_run.call_args[1]["cmd"]


@pytest.mark.asyncio
async def test_push_subtree_success(tmp_path):
    repo_dir = str(tmp_path)
    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        await push_subtree(repo_dir, "src/libA", "urlA", "main")
        mock_run.assert_called_once()
        assert "push" in mock_run.call_args[1]["cmd"]


@pytest.mark.asyncio
async def test_add_subtree_directory_exists(tmp_path):
    """Test add_subtree raises error when prefix directory exists."""
    repo_dir = str(tmp_path)
    existing_dir = tmp_path / "src" / "libA"
    existing_dir.mkdir(parents=True)

    with pytest.raises(ValueError) as exc_info:
        await add_subtree(
            repo_dir=repo_dir,
            name="libA",
            repo_url="urlA",
            branch="main",
            prefix=str(existing_dir),
        )
    assert "Directory exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_subtree_checks_the_prefix_inside_the_repository(
    tmp_path, monkeypatch
):
    """A relative prefix is relative to the repository, where `git subtree` runs,
    not to the directory zrb was started from."""
    repo_dir = tmp_path / "repo"
    (repo_dir / "src" / "libA").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        with pytest.raises(ValueError, match="Directory exists"):
            await add_subtree(
                repo_dir=str(repo_dir),
                name="libA",
                repo_url="urlA",
                branch="main",
                prefix="src/libA",
            )
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_add_subtree_ignores_a_same_named_directory_outside_the_repository(
    tmp_path, monkeypatch
):
    """A directory with the prefix's name under the current directory is not the
    subtree's destination, so it must not block the add."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "src" / "libA").mkdir(parents=True)
    monkeypatch.chdir(elsewhere)

    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        await add_subtree(
            repo_dir=str(repo_dir),
            name="libA",
            repo_url="urlA",
            branch="main",
            prefix="src/libA",
        )
        mock_run.assert_called_once()

    assert "libA" in load_config(str(repo_dir)).data


@pytest.mark.asyncio
async def test_add_subtree_name_exists(tmp_path):
    """Test add_subtree raises error when config name already exists."""
    repo_dir = str(tmp_path)
    # Create existing config
    config = SubTreeConfig(
        data={
            "libA": SingleSubTreeConfig(
                prefix="src/libA", repo_url="urlA", branch="main"
            )
        }
    )
    save_config(repo_dir, config)

    with pytest.raises(ValueError) as exc_info:
        await add_subtree(
            repo_dir=repo_dir,
            name="libA",  # Already exists
            repo_url="urlB",
            branch="main",
            prefix="src/libB",
        )
    assert "Subtree config already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_subtree_non_zero_exit(tmp_path):
    """Test add_subtree raises exception on non-zero exit code."""
    repo_dir = str(tmp_path)
    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "error", ""), 1)
        with pytest.raises(RuntimeError) as exc_info:
            await add_subtree(
                repo_dir=repo_dir,
                name="libA",
                repo_url="urlA",
                branch="main",
                prefix="src/libA",
            )
        assert "Non zero exit code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pull_subtree_non_zero_exit(tmp_path):
    """Test pull_subtree raises exception on non-zero exit code."""
    repo_dir = str(tmp_path)
    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "error", ""), 1)
        with pytest.raises(RuntimeError) as exc_info:
            await pull_subtree(repo_dir, "src/libA", "urlA", "main")
        assert "Non zero exit code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_push_subtree_non_zero_exit(tmp_path):
    """Test push_subtree raises exception on non-zero exit code."""
    repo_dir = str(tmp_path)
    with mock.patch(
        "zrb.git.subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "error", ""), 1)
        with pytest.raises(RuntimeError) as exc_info:
            await push_subtree(repo_dir, "src/libA", "urlA", "main")
        assert "Non zero exit code" in str(exc_info.value)
