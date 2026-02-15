import pytest
from unittest.mock import MagicMock
from zrb.llm.prompt.manager import PromptManager
from zrb.context.shared_context import SharedContext

def test_prompt_manager_basic():
    manager = PromptManager(
        prompts=["Static Prompt"],
        include_persona=False,
        include_mandate=False,
        include_system_context=False,
        include_note=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False
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
        include_note=True,
        include_claude_skills=True,
        include_cli_skills=True,
        include_project_context=True
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
        include_note=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False
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
        include_note=False,
        include_claude_skills=False,
        include_cli_skills=False,
        include_project_context=False
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
