import os
from unittest.mock import patch

import pytest

from zrb.llm.prompt.prompt import get_default_prompt


@pytest.fixture
def mock_cfg():
    with patch("zrb.llm.prompt.prompt.CFG") as mock:
        mock.LLM_PROMPT_DIR = ".zrb/llm/prompt"
        mock.ENV_PREFIX = "ZRB"
        yield mock


def test_get_default_prompt_traversal_to_home(mock_cfg, tmp_path):
    # Setup:
    # home: /tmp/home
    # project: /tmp/home/project
    # subdir: /tmp/home/project/subdir (CWD)

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

    with patch("os.getcwd", return_value=str(subdir)), patch(
        "os.path.expanduser", return_value=str(home)
    ):

        # 1. Should find project prompt by traversing up from subdir
        content = get_default_prompt("test_prompt")
        assert content == "Project Prompt Content"

        # 2. Should find home prompt by traversing up from subdir to home
        content = get_default_prompt("home_prompt")
        assert content == "Home Prompt Content"


def test_get_default_prompt_outside_home_no_traversal(mock_cfg, tmp_path):
    # Setup:
    # home: /tmp/home
    # other: /tmp/other (CWD)

    home = tmp_path / "home"
    home.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    # Prompt in a directory NOT on the path between other and root,
    # and definitely NOT under home.
    # But since it's in 'other', it should be found as 'current_path' is always searched.
    other_prompt_dir = other / ".zrb" / "llm" / "prompt"
    other_prompt_dir.mkdir(parents=True)
    other_prompt_file = other_prompt_dir / "other_prompt.md"
    other_prompt_file.write_text("Other Prompt Content")

    home_prompt_dir = home / ".zrb" / "llm" / "prompt"
    home_prompt_dir.mkdir(parents=True)
    home_prompt_file = home_prompt_dir / "home_prompt.md"
    home_prompt_file.write_text("Home Prompt Content")

    with patch("os.getcwd", return_value=str(other)), patch(
        "os.path.expanduser", return_value=str(home)
    ):

        # 1. Should find other prompt in CWD
        content = get_default_prompt("other_prompt")
        assert content == "Other Prompt Content"

        # 2. Should NOT find home prompt because other is not under home.
        # It should fallback to package default, which returns empty string
        # for 'home_prompt' as it's not a built-in prompt.
        content = get_default_prompt("home_prompt")
        assert content == ""


def test_get_default_prompt_fallback_to_package_default(mock_cfg):
    # Persona is a built-in prompt (raw file contains {ASSISTANT_NAME} placeholder)
    with patch("os.getcwd", return_value="/tmp/empty-dir"), patch(
        "os.path.expanduser", return_value="/home/user"
    ):

        content = get_default_prompt("persona")
        assert "You are" in content
        assert "assistant" in content.lower()


def test_get_default_prompt_env_override(mock_cfg, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PROMPT_TEST_PROMPT", "Env Prompt Content")

    with patch("os.getcwd", return_value="/tmp/empty-dir"), patch(
        "os.path.expanduser", return_value="/home/user"
    ):

        content = get_default_prompt("test_prompt")
        assert content == "Env Prompt Content"
