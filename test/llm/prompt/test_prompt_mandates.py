import os
import tempfile
from unittest.mock import patch

from zrb.llm.prompt.prompt import (
    get_git_mandate_prompt,
    get_journal_prompt,
    get_mandate_prompt,
    get_persona_prompt,
)


def test_get_persona_prompt_contains_core_identity():
    """Test get_persona_prompt contains the core identity section."""
    prompt = get_persona_prompt()
    assert "CORE IDENTITY" in prompt
    assert "Brownfield Specialist" in prompt
    assert "Pragmatic Doer" in prompt
    assert "Synthesizer" in prompt
    assert "Autonomous Agent" in prompt


def test_get_mandate_prompt_contains_operational_directives():
    """Test get_mandate_prompt contains the operational directives section."""
    prompt = get_mandate_prompt()
    assert "Mandate: Core Operational Directives" in prompt
    assert "Absolute Directives" in prompt
    assert "Execution Framework" in prompt
    assert "CLARIFY INTENT" in prompt
    # Ensure journaling mandate is removed
    assert "Consult Journal:" not in prompt
    assert "Journaling: Maintain" not in prompt


def test_get_git_mandate_prompt_contains_git_operations_protocol():
    """Test get_git_mandate_prompt contains the git operations protocol section."""
    prompt = get_git_mandate_prompt()
    assert "Git Operations Protocol" in prompt
    assert "User-Driven Commits" in prompt
    assert "Information Gathering" in prompt
    assert "Collaborative Workflow" in prompt


def test_get_journal_prompt_loads_journal_mandate():
    """Test get_journal_prompt loads the journal_mandate.md file."""
    prompt = get_journal_prompt()
    assert "Journal System: The Living Knowledge Graph" in prompt
    assert "Core Philosophy" in prompt
    assert "The Index File (`index.md`)" in prompt
    assert "Graph Structure Rules" in prompt


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
                assert "Local Journal Override" in prompt
                assert "This is a local override" in prompt
            finally:
                os.chdir(original_cwd)
