from unittest.mock import MagicMock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager, new_prompt


def test_prompt_manager_basic():
    manager = PromptManager(
        prompts=["Static Prompt"],
        include_persona=False,
        include_mandate=False,
        include_system_context=False,
        include_journal=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False,
    )

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "Static Prompt" in composed


def test_prompt_manager_all_includes():
    """Test with all include flags enabled to cover more branches."""
    manager = PromptManager(
        include_persona=True,
        include_mandate=True,
        include_system_context=True,
        include_journal=True,
        include_claude_skills=True,
        include_cli_skills=True,
        include_project_context=True,
    )

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    # Most of these are mocked or default to some content
    assert isinstance(composed, str)


def test_prompt_manager_add_prompt():
    manager = PromptManager(
        include_persona=False,
        include_mandate=False,
        include_system_context=False,
        include_journal=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False,
    )
    manager.add_prompt("P1")
    manager.append_prompt("P2")

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "P1" in composed
    assert "P2" in composed


def test_prompt_manager_middleware_types():
    def simple_prompt(ctx):
        return "Simple"

    def full_middleware(ctx, current, next_fn):
        return next_fn(ctx, current + "\nFull")

    manager = PromptManager(
        prompts=[simple_prompt, full_middleware, "String"],
        include_persona=False,
        include_mandate=False,
        include_system_context=False,
        include_journal=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False,
    )

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "Simple" in composed
    assert "Full" in composed
    assert "String" in composed


def test_prompt_manager_reset():
    manager = PromptManager(prompts=["P1"])
    manager.reset()
    assert len(manager.prompts) == 0


def test_prompt_manager_setters():
    manager = PromptManager()
    manager.prompts = ["New"]
    manager.active_skills = ["skill1"]
    manager.include_project_context = False

    assert manager.prompts == ["New"]
    assert manager.active_skills == ["skill1"]
    assert manager.include_project_context is False


def test_prompt_manager_all_property_getters_and_setters():
    """Test all include_* property getters and setters (lines 170-230)."""
    manager = PromptManager()

    # include_persona
    manager.include_persona = True
    assert manager.include_persona is True
    manager.include_persona = False
    assert manager.include_persona is False

    # include_mandate
    manager.include_mandate = True
    assert manager.include_mandate is True
    manager.include_mandate = False
    assert manager.include_mandate is False

    # include_git_mandate
    manager.include_git_mandate = True
    assert manager.include_git_mandate is True
    manager.include_git_mandate = False
    assert manager.include_git_mandate is False

    # include_system_context
    manager.include_system_context = True
    assert manager.include_system_context is True
    manager.include_system_context = False
    assert manager.include_system_context is False

    # include_journal
    manager.include_journal = True
    assert manager.include_journal is True
    manager.include_journal = False
    assert manager.include_journal is False

    # include_claude_skills
    manager.include_claude_skills = True
    assert manager.include_claude_skills is True
    manager.include_claude_skills = False
    assert manager.include_claude_skills is False

    # include_cli_skills
    manager.include_cli_skills = True
    assert manager.include_cli_skills is True
    manager.include_cli_skills = False
    assert manager.include_cli_skills is False

    # include_project_context (getter already tested above, setter covered here again)
    manager.include_project_context = True
    assert manager.include_project_context is True


def test_prompt_manager_render_true_with_string_prompt():
    """PromptManager(render=True) with a plain string prompt (line 261)."""
    manager = PromptManager(
        prompts=["Hello world"],
        render=True,
        include_persona=False,
        include_mandate=False,
        include_system_context=False,
        include_journal=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False,
    )
    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "Hello world" in composed


def test_new_prompt_with_render_true():
    """new_prompt(render=True) renders the prompt string via get_str_attr (line 325)."""
    middleware = new_prompt("Static content", render=True)
    ctx = SharedContext()

    result = middleware(ctx, "", lambda c, p: p)
    assert "Static content" in result
