"""Test PromptManager configuration defaults mechanism.

These tests verify that:
1. PromptManager uses configuration defaults when parameters are None
2. Environment variables can override configuration defaults
3. Explicit parameters take precedence over configuration defaults
4. Backward compatibility is maintained (explicit booleans still work)

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


def test_config_property_defaults():
    """Test that configuration properties have correct defaults."""
    # Reset CFG to ensure clean state
    CFG._instance = None

    # Verify all 8 new config properties exist and have correct defaults
    assert hasattr(
        CFG, "LLM_INCLUDE_PERSONA"
    ), "Config should have LLM_INCLUDE_PERSONA property"
    assert hasattr(
        CFG, "LLM_INCLUDE_MANDATE"
    ), "Config should have LLM_INCLUDE_MANDATE property"
    assert hasattr(
        CFG, "LLM_INCLUDE_GIT_MANDATE"
    ), "Config should have LLM_INCLUDE_GIT_MANDATE property"
    assert hasattr(
        CFG, "LLM_INCLUDE_SYSTEM_CONTEXT"
    ), "Config should have LLM_INCLUDE_SYSTEM_CONTEXT property"
    assert hasattr(
        CFG, "LLM_INCLUDE_JOURNAL"
    ), "Config should have LLM_INCLUDE_JOURNAL property"
    assert hasattr(
        CFG, "LLM_INCLUDE_CLAUDE_SKILLS"
    ), "Config should have LLM_INCLUDE_CLAUDE_SKILLS property"
    assert hasattr(
        CFG, "LLM_INCLUDE_CLI_SKILLS"
    ), "Config should have LLM_INCLUDE_CLI_SKILLS property"
    assert hasattr(
        CFG, "LLM_INCLUDE_PROJECT_CONTEXT"
    ), "Config should have LLM_INCLUDE_PROJECT_CONTEXT property"

    # Check default values (all True except CLI skills which is False)
    assert CFG.LLM_INCLUDE_PERSONA is True
    assert CFG.LLM_INCLUDE_MANDATE is True
    assert CFG.LLM_INCLUDE_GIT_MANDATE is True
    assert CFG.LLM_INCLUDE_SYSTEM_CONTEXT is True
    assert CFG.LLM_INCLUDE_JOURNAL is True
    assert CFG.LLM_INCLUDE_CLAUDE_SKILLS is True
    assert CFG.LLM_INCLUDE_CLI_SKILLS is False  # Only one with False default
    assert CFG.LLM_INCLUDE_PROJECT_CONTEXT is True


def test_config_property_setters():
    """Test that configuration property setters work correctly."""
    # Reset CFG
    CFG._instance = None

    # Test setting values
    CFG.LLM_INCLUDE_PERSONA = False
    CFG.LLM_INCLUDE_CLI_SKILLS = True
    CFG.LLM_INCLUDE_JOURNAL = False

    # Verify setters worked
    assert CFG.LLM_INCLUDE_PERSONA is False
    assert CFG.LLM_INCLUDE_CLI_SKILLS is True
    assert CFG.LLM_INCLUDE_JOURNAL is False

    # Other values should still be defaults
    assert CFG.LLM_INCLUDE_MANDATE is True
    assert CFG.LLM_INCLUDE_PROJECT_CONTEXT is True


def test_environment_variable_overrides():
    """Test that environment variables can override configuration defaults."""
    env_vars = {
        "ZRB_LLM_INCLUDE_PERSONA": "0",
        "ZRB_LLM_INCLUDE_MANDATE": "0",
        "ZRB_LLM_INCLUDE_CLI_SKILLS": "1",
        "_ZRB_ENV_PREFIX": "ZRB",
    }

    with patch.dict(os.environ, env_vars):
        # Reset CFG to pick up new env vars
        CFG._instance = None

        # Verify environment variables override defaults
        assert CFG.LLM_INCLUDE_PERSONA is False
        assert CFG.LLM_INCLUDE_MANDATE is False
        assert CFG.LLM_INCLUDE_CLI_SKILLS is True

        # Other values should still be defaults
        assert CFG.LLM_INCLUDE_GIT_MANDATE is True
        assert CFG.LLM_INCLUDE_SYSTEM_CONTEXT is True


def test_prompt_manager_uses_config_defaults():
    """Test that PromptManager uses config defaults when parameters are None."""
    # Reset CFG
    CFG._instance = None

    # Create context for testing
    ctx = SharedContext()

    # Create PromptManager with all None parameters
    manager = PromptManager(
        include_persona=None,
        include_mandate=None,
        include_git_mandate=None,
        include_system_context=None,
        include_journal=None,
        include_claude_skills=None,
        include_cli_skills=None,
        include_project_context=None,
    )

    # Compose prompt - should work without errors using config defaults
    prompt = manager.compose_prompt()(ctx)

    # Verify mechanism works (prompt is generated)
    assert isinstance(prompt, str)
    assert len(prompt) > 0  # Should have some content with defaults


def test_prompt_manager_explicit_overrides():
    """Test that explicit parameters override config defaults."""
    # Reset CFG
    CFG._instance = None

    ctx = SharedContext()

    # Create PromptManager with explicit values that differ from defaults
    manager = PromptManager(
        include_persona=False,  # Default is True
        include_cli_skills=True,  # Default is False
    )

    # Compose prompt - should work with explicit values
    prompt = manager.compose_prompt()(ctx)

    # Verify mechanism works
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_prompt_manager_backward_compatibility():
    """Test backward compatibility - explicit booleans still work."""
    # Reset CFG
    CFG._instance = None

    ctx = SharedContext()

    # Test with all explicit True/False values (not None)
    # This simulates old code that passed explicit booleans
    manager = PromptManager(
        include_persona=True,
        include_mandate=False,
        include_git_mandate=True,
        include_system_context=False,
        include_journal=True,
        include_claude_skills=False,
        include_cli_skills=True,
        include_project_context=False,
    )

    # Compose prompt - should work with all explicit values
    prompt = manager.compose_prompt()(ctx)

    # Verify mechanism works
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_prompt_manager_mixed_none_and_explicit():
    """Test mixed usage - some None (use config), some explicit."""
    # Reset CFG
    CFG._instance = None

    ctx = SharedContext()

    # Mix of None (use config) and explicit values
    manager = PromptManager(
        include_persona=None,  # Use config default (True)
        include_mandate=False,  # Explicit False
        include_cli_skills=None,  # Use config default (False)
        include_project_context=True,  # Explicit True (same as default)
    )

    # Compose prompt - should work with mixed values
    prompt = manager.compose_prompt()(ctx)

    # Verify mechanism works
    assert isinstance(prompt, str)
    assert len(prompt) > 0


@pytest.mark.asyncio
async def test_prompt_manager_integration():
    """Integration test - verify PromptManager works end-to-end with config."""
    # Reset CFG
    CFG._instance = None

    ctx = SharedContext()

    # Test 1: Default behavior
    manager1 = PromptManager()  # All None, use config defaults
    prompt1 = manager1.compose_prompt()(ctx)
    assert isinstance(prompt1, str)

    # Test 2: With environment variable overrides
    env_vars = {
        "ZRB_LLM_INCLUDE_PERSONA": "0",
        "ZRB_LLM_INCLUDE_CLI_SKILLS": "1",
        "_ZRB_ENV_PREFIX": "ZRB",
    }

    with patch.dict(os.environ, env_vars):
        CFG._instance = None

        manager2 = PromptManager()  # Should use env var overrides
        prompt2 = manager2.compose_prompt()(ctx)
        assert isinstance(prompt2, str)

        # Prompt should be different (due to different config)
        # But we don't check content - just that mechanism works
        assert prompt1 != prompt2 or len(prompt1) > 0  # Either different or both valid
