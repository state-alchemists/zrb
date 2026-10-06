import os
from unittest.mock import patch

import pytest

from zrb.llm.prompt.prompt import get_default_prompt


@pytest.fixture
def mock_cfg():
    with patch("zrb.llm.prompt.prompt.CFG") as mock:
        mock.LLM_PROMPT_DIR = ".zrb/llm/prompt"
        mock.ENV_PREFIX = "ZRB"
        mock.LLM_SEARCH_PROJECT = True
        mock.LLM_SEARCH_HOME = True
        yield mock


def test_get_default_prompt_traversal_to_home(mock_cfg, tmp_path):





    home = tmp_path / "home"
    project = home / "project"
    subdir = project / "subdir"
    subdir.mkdir(parents=True)

    prompt_dir = project / ".zrb" / "llm" / "prompt"
    prompt_dir.mkdir(parents=True)

    prompt_file = prompt_dir / "test_prompt.md"
    prompt_file.write_text("Project Prompt Content")

    home_prompt_dir = home / ".zrb" / "llm" / "prompt"
    home_prompt_dir.mkdir(parents=True)
    home_prompt_file = home_prompt_dir / "home_prompt.md"
    home_prompt_file.write_text("Home Prompt Content")

    with (
        patch("os.getcwd", return_value=str(subdir)),
        patch("os.path.expanduser", return_value=str(home)),
    ):


        content = get_default_prompt("test_prompt")
        assert content == "Project Prompt Content"


        content = get_default_prompt("home_prompt")
        assert content == "Home Prompt Content"


def test_get_default_prompt_home_reachable_outside_project_tree(mock_cfg, tmp_path):









    home = tmp_path / "home"
    home.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    other_prompt_dir = other / ".zrb" / "llm" / "prompt"
    other_prompt_dir.mkdir(parents=True)
    other_prompt_file = other_prompt_dir / "other_prompt.md"
    other_prompt_file.write_text("Other Prompt Content")

    home_prompt_dir = home / ".zrb" / "llm" / "prompt"
    home_prompt_dir.mkdir(parents=True)
    home_prompt_file = home_prompt_dir / "home_prompt.md"
    home_prompt_file.write_text("Home Prompt Content")

    with (
        patch("os.getcwd", return_value=str(other)),
        patch("os.path.expanduser", return_value=str(home)),
    ):


        content = get_default_prompt("other_prompt")
        assert content == "Other Prompt Content"


        content = get_default_prompt("home_prompt")
        assert content == "Home Prompt Content"


def test_get_default_prompt_home_layer_off_when_search_home_disabled(
    mock_cfg, tmp_path
):


    mock_cfg.LLM_SEARCH_HOME = False

    home = tmp_path / "home"
    home.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    home_prompt_dir = home / ".zrb" / "llm" / "prompt"
    home_prompt_dir.mkdir(parents=True)
    home_prompt_file = home_prompt_dir / "home_prompt_disabled.md"
    home_prompt_file.write_text("Home Prompt Content")

    with (
        patch("os.getcwd", return_value=str(other)),
        patch("os.path.expanduser", return_value=str(home)),
    ):
        content = get_default_prompt("home_prompt_disabled")
        assert content == ""


def test_get_default_prompt_fallback_to_package_default(mock_cfg):

    with (
        patch("os.getcwd", return_value="/tmp/empty-dir"),
        patch("os.path.expanduser", return_value="/home/user"),
    ):

        content = get_default_prompt("persona")
        assert isinstance(content, str)
        assert len(content) > 0

        assert "{ASSISTANT_NAME}" in content


def test_get_default_prompt_env_override(mock_cfg, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PROMPT_TEST_PROMPT", "Env Prompt Content")

    with (
        patch("os.getcwd", return_value="/tmp/empty-dir"),
        patch("os.path.expanduser", return_value="/home/user"),
    ):

        content = get_default_prompt("test_prompt")
        assert content == "Env Prompt Content"
