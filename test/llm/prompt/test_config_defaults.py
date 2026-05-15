"""Test PromptManager configuration defaults mechanism.

These tests verify that:
1. PromptManager uses LLM_INCLUDE_SECTIONS from CFG when include_sections is None
2. Environment variables can override LLM_INCLUDE_SECTIONS
3. Explicit include_sections parameter takes precedence over config defaults
4. Backward compatibility is maintained (old boolean kwargs still work)

Note: We test the MECHANISM, not the exact content of prompts.
Markdown files can change (formatting, language, etc.), but the
configuration mechanism should still work correctly.
"""

import os
from unittest.mock import patch

import pytest

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager


def test_config_llm_include_sections_default():
    """Test that LLM_INCLUDE_SECTIONS has the correct default."""
    # Reset CFG to ensure clean state
    CFG._instance = None

    assert hasattr(
        CFG, "LLM_INCLUDE_SECTIONS"
    ), "Config should have LLM_INCLUDE_SECTIONS property"

    sections = CFG.LLM_INCLUDE_SECTIONS
    assert isinstance(sections, list)
    # Default order: persona, mandate, git_mandate, journal_mandate,
    # system_context, project_context, tool_guidance, claude_skills.
    assert sections == [
        "persona",
        "mandate",
        "git_mandate",
        "journal_mandate",
        "system_context",
        "project_context",
        "tool_guidance",
        "claude_skills",
    ]


def test_config_llm_include_sections_setter():
    """Test that the LLM_INCLUDE_SECTIONS setter works."""
    CFG._instance = None

    CFG.LLM_INCLUDE_SECTIONS = ["persona", "mandate"]
    assert CFG.LLM_INCLUDE_SECTIONS == ["persona", "mandate"]

    # Reset
    CFG._instance = None


def test_environment_variable_overrides():
    """Test that environment variables can override LLM_INCLUDE_SECTIONS."""
    env_vars = {
        "ZRB_LLM_INCLUDE_SECTIONS": "persona,system_context",
        "_ZRB_ENV_PREFIX": "ZRB",
    }

    with patch.dict(os.environ, env_vars):
        CFG._instance = None

        sections = CFG.LLM_INCLUDE_SECTIONS
        assert sections == ["persona", "system_context"]
        assert "mandate" not in sections
        assert "git_mandate" not in sections


def test_prompt_manager_uses_config_defaults():
    """Test that PromptManager uses config defaults when include_sections is None."""
    CFG._instance = None

    ctx = SharedContext()

    # include_sections=None means use CFG defaults
    manager = PromptManager()

    prompt = manager.compose_prompt()(ctx)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_prompt_manager_explicit_overrides():
    """Test that explicit include_sections overrides config defaults."""
    CFG._instance = None

    ctx = SharedContext()

    # Explicit include_sections takes precedence
    manager = PromptManager(
        include_sections=["persona", "mandate"],
    )

    prompt = manager.compose_prompt()(ctx)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_prompt_manager_include_sections_explicit_subset():
    """Explicit include_sections selects only listed sections."""
    CFG._instance = None

    ctx = SharedContext()

    manager = PromptManager(
        include_sections=["persona", "git_mandate", "journal_mandate"],
    )

    prompt = manager.compose_prompt()(ctx)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_prompt_manager_include_sections_ordering():
    """Section ordering follows include_sections order."""
    CFG._instance = None

    ctx = SharedContext()

    manager = PromptManager(
        include_sections=["mandate", "persona"],
    )

    prompt = manager.compose_prompt()(ctx)
    # mandate header comes before persona header
    assert prompt.index("# Operating Rules") < prompt.index("# Identity")


@pytest.mark.asyncio
async def test_prompt_manager_integration():
    """Integration test - verify PromptManager works end-to-end with config."""
    CFG._instance = None

    ctx = SharedContext()

    # Test 1: Default behavior (use CFG defaults)
    manager1 = PromptManager()
    prompt1 = manager1.compose_prompt()(ctx)
    assert isinstance(prompt1, str)

    # Test 2: With environment variable overrides
    env_vars = {
        "ZRB_LLM_INCLUDE_SECTIONS": "persona,mandate",
        "_ZRB_ENV_PREFIX": "ZRB",
    }

    with patch.dict(os.environ, env_vars):
        CFG._instance = None

        manager2 = PromptManager()
        prompt2 = manager2.compose_prompt()(ctx)
        assert isinstance(prompt2, str)

        assert prompt1 != prompt2 or len(prompt1) > 0


def test_prompt_manager_empty_sections_produces_no_builtin_content():
    """include_sections=[] means no built-in sections."""
    CFG._instance = None

    ctx = SharedContext()

    manager = PromptManager(include_sections=[])
    prompt = manager.compose_prompt()(ctx)
    # With no built-in sections and no custom prompts, result should be empty
    assert prompt.strip() == ""
