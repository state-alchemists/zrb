"""Tests for the journal prompt function."""

import os
import tempfile
from unittest.mock import patch

import pytest

from zrb.llm.prompt.prompt import get_journal_prompt


def test_get_journal_prompt_returns_default():
    """Test get_journal_prompt returns the default journal prompt."""
    prompt = get_journal_prompt()
    assert prompt is not None
    assert len(prompt) > 0
    # Should contain journal system configuration
    assert "Journal System" in prompt
    assert "Configuration:" in prompt
    assert "Core Philosophy:" in prompt
    assert "Journaling Rules:" in prompt


def test_get_journal_prompt_with_local_override():
    """Test get_journal_prompt uses local override when available."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local journal.md file
        local_prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(local_prompt_dir, exist_ok=True)
        local_journal_path = os.path.join(local_prompt_dir, "journal.md")
        local_content = "# Local Journal Override\n\nThis is a local override."
        with open(local_journal_path, "w") as f:
            f.write(local_content)

        # Mock CFG to use our temp directory
        with patch("zrb.llm.prompt.prompt.CFG") as mock_cfg:
            mock_cfg.LLM_PROMPT_DIR = ".zrb/llm/prompt"
            mock_cfg.ENV_PREFIX = "ZRB"

            # Change to temp directory and get prompt
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                prompt = get_journal_prompt()
                assert "Local Journal Override" in prompt
                assert "This is a local override" in prompt
            finally:
                os.chdir(original_cwd)


def test_get_journal_prompt_with_environment_variable():
    """Test get_journal_prompt uses environment variable when set."""
    # Set environment variable
    os.environ["ZRB_LLM_PROMPT_JOURNAL"] = "# Env Journal\n\nFrom environment variable."

    try:
        # Mock CFG
        with patch("zrb.llm.prompt.prompt.CFG") as mock_cfg:
            mock_cfg.ENV_PREFIX = "ZRB"
            mock_cfg.LLM_PROMPT_DIR = ".zrb/llm/prompt"

            prompt = get_journal_prompt()
            assert "Env Journal" in prompt
            assert "From environment variable" in prompt
    finally:
        # Clean up
        del os.environ["ZRB_LLM_PROMPT_JOURNAL"]


def test_get_journal_prompt_replaces_placeholders():
    """Test get_journal_prompt replaces configuration placeholders."""
    with patch("zrb.llm.prompt.prompt.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = "/test/journal/dir"
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "test_index.md"
        mock_cfg.ENV_PREFIX = "ZRB"

        prompt = get_journal_prompt()
        assert "/test/journal/dir" in prompt
        assert "test_index.md" in prompt
        # Should not contain raw placeholders
        assert "{CFG_LLM_JOURNAL_DIR}" not in prompt
        assert "{CFG_LLM_JOURNAL_INDEX_FILE}" not in prompt


def test_get_journal_prompt_returns_empty_string_when_missing():
    """Test get_journal_prompt returns empty string when journal.md doesn't exist."""
    # Temporarily rename the journal.md file
    journal_path = "src/zrb/llm/prompt/markdown/journal.md"
    temp_path = "src/zrb/llm/prompt/markdown/journal.md.bak"

    if os.path.exists(journal_path):
        os.rename(journal_path, temp_path)

    try:
        prompt = get_journal_prompt()
        assert prompt == ""
    finally:
        # Restore the file
        if os.path.exists(temp_path):
            os.rename(temp_path, journal_path)
