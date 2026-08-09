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


def test_get_prompt_workflow_returns_non_empty():
    """get_prompt('workflow') returns a non-empty string."""
    prompt = get_prompt("workflow")
    assert isinstance(prompt, str)
    assert prompt.strip() != ""


def test_get_prompt_workflow_carries_the_absorbed_sections():
    """`workflow` is the sole home of the Priority Order and the git rule.

    No other section carries them, so if they were dropped from `workflow`
    nothing else would notice.
    """
    prompt = get_prompt("workflow")
    assert "## Priority Order" in prompt
    assert "git diff HEAD" in prompt


def test_get_prompt_retired_section_resolves_to_empty():
    """A retired name left in a pinned config is a no-op, not a crash."""
    for name in ("mandate", "git_mandate", "journal_mandate", "tool_guidance"):
        assert get_prompt(name) == ""


def test_get_prompt_workflow_with_local_override():
    """get_prompt('workflow') uses local override when available."""
    with tempfile.TemporaryDirectory() as temp_dir:
        local_prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(local_prompt_dir, exist_ok=True)
        with open(os.path.join(local_prompt_dir, "workflow.md"), "w") as f:
            f.write("# Local Workflow Override\n\nThis is a local override.")

        env_vars = {
            "ZRB_LLM_PROMPT_DIR": ".zrb/llm/prompt",
            "_ZRB_ENV_PREFIX": "ZRB",
        }
        with patch.dict(os.environ, env_vars):
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                prompt = get_prompt("workflow")
                assert "Local Workflow Override" in prompt
            finally:
                os.chdir(original_cwd)


# ── Profile variants (ADR-0049) ──────────────────────────────────────────


def test_get_prompt_minimal_profile_uses_variant_when_present():
    """profile='minimal' resolves persona.minimal.md, not the base file."""
    base = get_prompt("persona", ASSISTANT_NAME="Zrb")
    explicit = get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb")
    assert explicit != base


def test_get_prompt_profile_falls_back_when_no_variant():
    """A section with no variant file transparently resolves to its base.

    Exercised on a non-section prompt file. Every *section* now ships a variant
    per preset — that is the point of the burden ladder in
    ``test_section_composition.py`` — so a section can no longer demonstrate
    the fallback without first regressing the thing the ladder pins.
    """
    base = get_prompt("web_summarizer")
    explicit = get_prompt("web_summarizer", profile="minimal")
    assert explicit == base


def test_get_prompt_full_profile_uses_base_file():
    """The base files ARE the `full` profile — no .full variant is consulted."""
    base = get_prompt("persona", ASSISTANT_NAME="Zrb")
    full = get_prompt("persona", profile="full", ASSISTANT_NAME="Zrb")
    assert full == base


def test_get_prompt_profile_falls_back_to_base_when_no_variant():
    """A section with no variant for the profile falls back to the base file.

    Pinned on a prompt file that is genuinely preset-invariant, never on a
    *section*: every section ships a variant per preset, so pinning the fallback
    on one would pin the absence of a variant somebody still has to write.
    """
    base = get_prompt("repo_summarizer")
    assert get_prompt("repo_summarizer", profile="minimal") == base


def test_get_prompt_examples_ships_demonstrations():
    """`examples` is one file with no variant, and it carries worked examples.

    `minimal` drops the section rather than re-wording it, carrying its own
    demonstrations inline in `workflow.minimal.md`, so there is no second file
    here to keep in step.
    """
    base = get_prompt("examples")
    assert "<example>" in base
    assert get_prompt("examples", profile="minimal") == base


def test_get_prompt_variant_respects_local_override():
    """A project override of the variant file wins over the packaged variant."""
    with tempfile.TemporaryDirectory() as temp_dir:
        local_prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(local_prompt_dir, exist_ok=True)
        with open(os.path.join(local_prompt_dir, "persona.minimal.md"), "w") as f:
            f.write("# Custom Explicit Persona Override")

        env_vars = {
            "ZRB_LLM_PROMPT_DIR": ".zrb/llm/prompt",
            "_ZRB_ENV_PREFIX": "ZRB",
        }
        with patch.dict(os.environ, env_vars):
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                prompt = get_prompt("persona", profile="minimal")
                assert "Custom Explicit Persona Override" in prompt
            finally:
                os.chdir(original_cwd)
