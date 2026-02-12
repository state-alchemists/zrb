import os
from unittest import mock

import pytest

from zrb.cmd.cmd_result import CmdResult
from zrb.util.git_subtree import (
    add_subtree,
    load_config,
    pull_subtree,
    push_subtree,
    save_config,
)
from zrb.util.git_subtree_model import SingleSubTreeConfig, SubTreeConfig


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
        "zrb.util.git_subtree.run_command", new_callable=mock.AsyncMock
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
        "zrb.util.git_subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        await pull_subtree(repo_dir, "src/libA", "urlA", "main")
        mock_run.assert_called_once()
        # Verify it was a pull command
        assert "pull" in mock_run.call_args[1]["cmd"]


@pytest.mark.asyncio
async def test_push_subtree_success(tmp_path):
    repo_dir = str(tmp_path)
    with mock.patch(
        "zrb.util.git_subtree.run_command", new_callable=mock.AsyncMock
    ) as mock_run:
        mock_run.return_value = (CmdResult("", "", ""), 0)
        await push_subtree(repo_dir, "src/libA", "urlA", "main")
        mock_run.assert_called_once()
        # Verify it was a push command
        assert "push" in mock_run.call_args[1]["cmd"]
