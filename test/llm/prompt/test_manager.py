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


# ── Tool guidance ─────────────────────────────────────────────────────────────


def _guidance_manager(**extra) -> PromptManager:
    """Helper: a PromptManager with all built-in sections off except tool_guidance."""
    return PromptManager(
        include_persona=False,
        include_mandate=False,
        include_system_context=False,
        include_journal=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False,
        include_tool_guidance=True,
        **extra,
    )


def test_add_tool_guidance_appears_in_prompt():
    manager = _guidance_manager()
    manager.add_tool_guidance(
        group="MyGroup",
        name="MyTool",
        use_when="Doing something useful",
        key_rule="Always pass --flag.",
    )
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert "MyGroup" in result
    assert "MyTool" in result
    assert "Doing something useful" in result
    assert "Always pass --flag." in result


def test_add_tool_guidance_without_key_rule():
    manager = _guidance_manager()
    manager.add_tool_guidance(group="G", name="Tool", use_when="Does stuff")
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert "Tool" in result
    assert "Does stuff" in result
    assert " — *" not in result


def test_add_tool_guidance_auto_creates_group():
    manager = _guidance_manager()
    manager.add_tool_guidance(group="AutoGroup", name="AutoTool", use_when="Auto use")
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert "AutoGroup" in result
    assert "AutoTool" in result


def test_add_tool_group_is_idempotent():
    manager = _guidance_manager()
    manager.add_tool_group(name="GroupA")
    manager.add_tool_group(name="GroupA")  # second call is a no-op
    manager.add_tool_guidance(group="GroupA", name="Tool1", use_when="Does stuff")
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert result.count("GroupA") == 1  # header rendered exactly once


def test_add_tool_guidance_updates_existing_entry():
    manager = _guidance_manager()
    manager.add_tool_guidance(group="G", name="Tool", use_when="Old description")
    manager.add_tool_guidance(group="G", name="Tool", use_when="New description")
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert "New description" in result
    assert "Old description" not in result


def test_tool_guidance_absent_when_no_entries_registered():
    manager = _guidance_manager()
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert "Tool Usage Guide" not in result


def test_tool_names_filter_excludes_unregistered_tools():
    manager = _guidance_manager(tool_names={"ToolA"})
    manager.add_tool_guidance(group="G", name="ToolA", use_when="Does A")
    manager.add_tool_guidance(group="G", name="ToolB", use_when="Does B")
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert "ToolA" in result
    assert "ToolB" not in result


def test_multiple_groups_appear_in_registration_order():
    manager = _guidance_manager()
    manager.add_tool_guidance(group="First", name="T1", use_when="Use T1")
    manager.add_tool_guidance(group="Second", name="T2", use_when="Use T2")
    ctx = SharedContext()
    result = manager.compose_prompt()(ctx)
    assert result.index("First") < result.index("Second")
