import os
import tempfile
from unittest.mock import patch

from zrb.llm.prompt.prompt import (
    get_git_mandate_prompt,
    get_journal_prompt,
    get_mandate_prompt,
    get_persona_prompt,
)


def test_get_persona_prompt_returns_non_empty():
    """Test get_persona_prompt returns a non-empty string with placeholder replaced."""
    prompt = get_persona_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    # Should contain the assistant name placeholder replacement
    assert "zrb" in prompt  # Default assistant name from CFG
    # Should not contain raw placeholder
    assert "{ASSISTANT_NAME}" not in prompt


def test_get_persona_prompt_with_custom_name():
    """Test get_persona_prompt accepts custom assistant name."""
    prompt = get_persona_prompt("CustomAssistant")
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "CustomAssistant" in prompt
    assert "{ASSISTANT_NAME}" not in prompt


def test_get_mandate_prompt_returns_non_empty():
    """Test get_mandate_prompt returns a non-empty string."""
    prompt = get_mandate_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    # Should contain meaningful content (not just whitespace)
    assert prompt.strip() != ""


def test_get_git_mandate_prompt_returns_non_empty():
    """Test get_git_mandate_prompt returns a non-empty string."""
    prompt = get_git_mandate_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert prompt.strip() != ""


def test_get_journal_prompt_returns_non_empty():
    """Test get_journal_prompt returns a non-empty string."""
    prompt = get_journal_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert prompt.strip() != ""


def test_get_journal_prompt_replaces_placeholders():
    """Test get_journal_prompt replaces configuration placeholders."""
    # Patch environment variables to influence CFG
    env_vars = {
        "ZRB_LLM_JOURNAL_DIR": "/test/journal/dir",
        "ZRB_LLM_JOURNAL_INDEX_FILE": "test_index.md",
        "_ZRB_ENV_PREFIX": "ZRB",
    }
    with patch.dict(os.environ, env_vars):
        prompt = get_journal_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should contain replaced values
        assert "/test/journal/dir" in prompt
        assert "test_index.md" in prompt
        # Should not contain raw placeholders
        assert "{CFG_LLM_JOURNAL_DIR}" not in prompt
        assert "{CFG_LLM_JOURNAL_INDEX_FILE}" not in prompt


def test_get_journal_prompt_with_local_override():
    """Test get_journal_prompt uses local override when available."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local journal_mandate.md file (renamed from journal.md)
        local_prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(local_prompt_dir, exist_ok=True)
        local_journal_path = os.path.join(local_prompt_dir, "journal_mandate.md")
        local_content = "# Local Journal Override\n\nThis is a local override."
        with open(local_journal_path, "w") as f:
            f.write(local_content)

        # Patch environment variables to influence CFG
        env_vars = {
            "ZRB_LLM_PROMPT_DIR": ".zrb/llm/prompt",
            "_ZRB_ENV_PREFIX": "ZRB",
        }
        with patch.dict(os.environ, env_vars):
            # Change to temp directory and get prompt
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # We need to make sure _get_default_prompt_search_path returns the temp_dir
                # The logic uses os.getcwd(), so changing dir should work.
                prompt = get_journal_prompt()
                assert isinstance(prompt, str)
                assert len(prompt) > 0
                # Should contain local override content
                assert "Local Journal Override" in prompt
                assert "This is a local override" in prompt
            finally:
                os.chdir(original_cwd)
