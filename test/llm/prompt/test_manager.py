"""Public PromptManager behavior."""

from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager, new_prompt


def test_explicit_sections_control_composition():
    prompt = PromptManager(
        include_sections=["principle", "workflow"], skill_manager=None
    ).compose_prompt()(SharedContext())
    assert "# Principle" in prompt
    assert "# Workflow" in prompt
    assert "# Persona" not in prompt


def test_profile_section_uses_the_active_profile(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PROFILE", "capable")
    prompt = PromptManager(
        include_sections=["profile"], skill_manager=None
    ).compose_prompt()(SharedContext())
    assert "Take strong ownership" in prompt


def test_appended_prompts_and_middleware_remain_supported():
    def simple_prompt(ctx):
        return "Simple"

    manager = PromptManager(prompts=[simple_prompt, "Static"], include_sections=[])
    manager.append_prompt(new_prompt("Middleware"))
    prompt = manager.compose_prompt()(SharedContext())
    assert "Simple" in prompt
    assert "Static" in prompt
    assert "Middleware" in prompt


def test_reset_removes_only_appended_prompts():
    manager = PromptManager(prompts=["P1"])
    manager.reset()
    assert manager.prompts == []


def test_live_context_remains_outside_system_sections():
    manager = PromptManager(include_sections=[])
    context = manager.create_live_context(SharedContext())
    assert context.startswith("<live-context>")


def test_default_prompt_carries_system_and_project_context():
    prompt = PromptManager(skill_manager=None).compose_prompt()(SharedContext())
    assert "# System Context" in prompt
    assert "# Project Context" in prompt


def test_system_context_renders_stable_environment_facts():
    prompt = PromptManager(
        include_sections=["system_context"], skill_manager=None
    ).compose_prompt()(SharedContext())
    assert "# System Context" in prompt
    assert "- CWD:" in prompt


def test_project_context_is_a_composable_section():
    prompt = PromptManager(
        include_sections=["project_context"], skill_manager=None
    ).compose_prompt()(SharedContext())
    assert "# Project Context" in prompt


def test_unknown_section_names_are_ignored():
    prompt = PromptManager(
        include_sections=["persona", "not-a-section"], skill_manager=None
    ).compose_prompt()(SharedContext())
    assert "# Persona" in prompt
