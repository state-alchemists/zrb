import os
import tempfile
from unittest.mock import patch

from zrb.config.config import CFG
from zrb.llm.prompt.prompt import get_prompt


def test_get_prompt_persona_returns_non_empty():
    """get_prompt('persona') with ASSISTANT_NAME returns non-empty."""
    prompt = get_prompt("persona", ASSISTANT_NAME=CFG.LLM_ASSISTANT_NAME)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert CFG.LLM_ASSISTANT_NAME in prompt
    assert "{ASSISTANT_NAME}" not in prompt


def test_get_prompt_persona_with_custom_name():
    """get_prompt('persona') with custom ASSISTANT_NAME."""
    prompt = get_prompt("persona", ASSISTANT_NAME="CustomAssistant")
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "CustomAssistant" in prompt
    assert "{ASSISTANT_NAME}" not in prompt


def test_get_prompt_mandate_returns_non_empty():
    """get_prompt('mandate') returns a non-empty string."""
    prompt = get_prompt("mandate")
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert prompt.strip() != ""


def test_get_prompt_git_mandate_returns_non_empty():
    """get_prompt('git_mandate') returns a non-empty string."""
    prompt = get_prompt("git_mandate")
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert prompt.strip() != ""


def test_get_prompt_journal_mandate_returns_non_empty():
    """get_prompt('journal_mandate') returns a non-empty string."""
    prompt = get_prompt("journal_mandate")
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert prompt.strip() != ""


def test_get_prompt_journal_mandate_replaces_placeholders():
    """get_prompt('journal_mandate') replaces configuration placeholders."""
    env_vars = {
        "ZRB_LLM_JOURNAL_DIR": "/test/journal/dir",
        "ZRB_LLM_JOURNAL_INDEX_FILE": "test_index.md",
        "_ZRB_ENV_PREFIX": "ZRB",
    }
    with patch.dict(os.environ, env_vars):
        prompt = get_prompt("journal_mandate")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "/test/journal/dir" in prompt
        assert "test_index.md" in prompt
        assert "{CFG_LLM_JOURNAL_DIR}" not in prompt
        assert "{CFG_LLM_JOURNAL_INDEX_FILE}" not in prompt


def test_get_prompt_journal_mandate_with_local_override():
    """get_prompt('journal_mandate') uses local override when available."""
    with tempfile.TemporaryDirectory() as temp_dir:
        local_prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(local_prompt_dir, exist_ok=True)
        local_journal_path = os.path.join(local_prompt_dir, "journal_mandate.md")
        local_content = "# Local Journal Override\n\nThis is a local override."
        with open(local_journal_path, "w") as f:
            f.write(local_content)

        env_vars = {
            "ZRB_LLM_PROMPT_DIR": ".zrb/llm/prompt",
            "_ZRB_ENV_PREFIX": "ZRB",
        }
        with patch.dict(os.environ, env_vars):
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                prompt = get_prompt("journal_mandate")
                assert isinstance(prompt, str)
                assert len(prompt) > 0
                assert "Local Journal Override" in prompt
                assert "This is a local override" in prompt
            finally:
                os.chdir(original_cwd)


# ── Profile variants (ADR-0083) ──────────────────────────────────────────


def test_get_prompt_explicit_profile_uses_variant_when_present():
    """profile='explicit' resolves persona.explicit.md, not the base file."""
    base = get_prompt("persona", ASSISTANT_NAME="Zrb")
    explicit = get_prompt("persona", profile="explicit", ASSISTANT_NAME="Zrb")
    assert explicit != base
    assert "No preamble" in explicit  # text unique to the explicit variant


def test_get_prompt_terse_profile_uses_base_file():
    """The base files ARE the terse profile — no .terse variant is consulted."""
    base = get_prompt("persona", ASSISTANT_NAME="Zrb")
    terse = get_prompt("persona", profile="terse", ASSISTANT_NAME="Zrb")
    assert terse == base


def test_get_prompt_profile_falls_back_to_base_when_no_variant():
    """A section with no variant for the profile falls back to the base file."""
    base = get_prompt("mandate")
    explicit = get_prompt("mandate", profile="explicit")
    assert explicit == base


def test_get_prompt_examples_section_is_explicit_only():
    """The examples section ships as an explicit-profile variant."""
    assert "Worked Examples" in get_prompt("examples", profile="explicit")


def test_get_prompt_variant_respects_local_override():
    """A project override of the variant file wins over the packaged variant."""
    with tempfile.TemporaryDirectory() as temp_dir:
        local_prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(local_prompt_dir, exist_ok=True)
        with open(os.path.join(local_prompt_dir, "persona.explicit.md"), "w") as f:
            f.write("# Custom Explicit Persona Override")

        env_vars = {
            "ZRB_LLM_PROMPT_DIR": ".zrb/llm/prompt",
            "_ZRB_ENV_PREFIX": "ZRB",
        }
        with patch.dict(os.environ, env_vars):
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                prompt = get_prompt("persona", profile="explicit")
                assert "Custom Explicit Persona Override" in prompt
            finally:
                os.chdir(original_cwd)
