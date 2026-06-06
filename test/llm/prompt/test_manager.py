from unittest.mock import MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager, new_prompt


def test_prompt_manager_basic():
    manager = PromptManager(
        prompts=["Static Prompt"],
        include_sections=[],
    )

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "Static Prompt" in composed


def test_prompt_manager_include_sections():
    """Test that include_sections controls which sections appear."""
    manager = PromptManager(
        include_sections=["persona", "mandate", "system_context"],
    )

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert isinstance(composed, str)
    assert len(composed) > 0


def test_prompt_manager_empty_sections():
    """include_sections=[] means no built-in sections, only custom prompts."""
    manager = PromptManager(
        prompts=["Custom Only"],
        include_sections=[],
    )

    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "Custom Only" in composed
    # Core sections should NOT appear
    assert "# Identity" not in composed
    assert "# Operating Rules" not in composed


def test_prompt_manager_add_prompt():
    manager = PromptManager(include_sections=[])
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
        include_sections=[],
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
    manager.include_sections = ["mandate"]

    assert manager.prompts == ["New"]
    assert manager.active_skills == ["skill1"]
    assert manager.include_sections == ["mandate"]


def test_prompt_manager_include_sections_property():
    """Test get/set of include_sections property."""
    manager = PromptManager()
    assert manager.include_sections is None  # default: use CFG

    manager.include_sections = ["persona", "system_context"]
    assert manager.include_sections == ["persona", "system_context"]

    manager.include_sections = None
    assert manager.include_sections is None


def test_prompt_manager_model_property_defaults_to_none():
    """``PromptManager.model`` starts unset; set by the task runner."""
    manager = PromptManager()
    assert manager.model is None
    manager.model = "openai:gpt-4o"
    assert manager.model == "openai:gpt-4o"


def test_prompt_manager_threads_model_into_system_context():
    """``model`` set on the manager appears in the rendered system context — identity only."""
    manager = PromptManager(include_sections=["system_context"])
    manager.model = "ollama:minimax-m2.7:cloud"

    ctx = MagicMock()
    ctx.input.session = "manager-model-test"
    composed = manager.compose_prompt()
    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = composed(ctx)

    assert "- Model: ollama:minimax-m2.7:cloud" in rendered
    # The capability warning is in Tool Usage Guide, not system context.
    assert "CRITICAL" not in rendered


def test_prompt_manager_tool_guidance_sections_injected_before_catalogue():
    """`tool_guidance_sections` content appears in the Tool Usage Guide output."""
    manager = PromptManager(include_sections=["tool_guidance"])
    manager.tool_guidance_sections = ["## Tool Call Parallelism\n- ⛔ Test warning."]

    ctx = MagicMock()
    composed = manager.compose_prompt()
    rendered = composed(ctx)

    assert "# Tool Usage Guide" in rendered
    assert "## Tool Call Parallelism" in rendered
    assert "Test warning." in rendered


def test_prompt_manager_render_true_with_string_prompt():
    """PromptManager(render=True) with a plain string prompt."""
    manager = PromptManager(
        prompts=["Hello world"],
        render=True,
        include_sections=[],
    )
    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "Hello world" in composed


def test_new_prompt_with_render_true():
    """new_prompt(render=True) renders the prompt string via get_str_attr."""
    middleware = new_prompt("Static content", render=True)
    ctx = SharedContext()

    result = middleware(ctx, "", lambda c, p: p)
    assert "Static content" in result


# ── Section ordering ──────────────────────────────────────────────────────────


def test_section_order_follows_include_sections():
    """Sections appear in the order specified by include_sections."""
    manager = PromptManager(
        include_sections=["mandate", "persona"],
    )
    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    # "mandate" section starts with "# Operating Rules", "persona" with "# Identity"
    mandate_pos = composed.index("# Operating Rules")
    persona_pos = composed.index("# Identity")
    assert mandate_pos < persona_pos

    # Reverse order
    manager2 = PromptManager(
        include_sections=["persona", "mandate"],
    )
    composed2 = manager2.compose_prompt()(ctx)
    persona_pos2 = composed2.index("# Identity")
    mandate_pos2 = composed2.index("# Operating Rules")
    assert persona_pos2 < mandate_pos2


# ── Custom file-backed sections ───────────────────────────────────────────────


def test_unknown_section_loads_via_get_prompt():
    """An unknown section name is resolved as a file-backed custom section."""
    manager = PromptManager(include_sections=["persona", "company_context"])
    ctx = SharedContext()
    with patch(
        "zrb.llm.prompt.manager.get_prompt",
        side_effect=lambda name, **kw: (
            "# Company Context" if name == "company_context" else f"# {name}"
        ),
    ):
        composed = manager.compose_prompt()(ctx)
    assert "# Company Context" in composed


def test_custom_section_follows_include_order():
    """A custom section appears at its configured position, not last."""
    manager = PromptManager(include_sections=["persona", "company_context", "mandate"])
    ctx = SharedContext()
    with patch(
        "zrb.llm.prompt.manager.get_prompt",
        side_effect=lambda name, **kw: (
            "# Company Context"
            if name == "company_context"
            else ("# Identity" if name == "persona" else "# Operating Rules")
        ),
    ):
        composed = manager.compose_prompt()(ctx)
    assert (
        composed.index("# Identity")
        < composed.index("# Company Context")
        < composed.index("# Operating Rules")
    )


def test_missing_custom_section_is_harmless():
    """A custom section with no backing file resolves to empty (no crash)."""
    manager = PromptManager(include_sections=["does_not_exist"])
    ctx = SharedContext()
    with patch("zrb.llm.prompt.manager.get_prompt", return_value=""):
        composed = manager.compose_prompt()(ctx)
    assert composed.strip() == ""


# ── Registered dynamic sections ───────────────────────────────────────────────


def test_registered_section_is_composed_dynamically():
    """A registered provider is composed by calling it with the context."""
    manager = PromptManager(include_sections=["persona", "live_status"])
    manager.register_section("live_status", lambda ctx: "# Live Status")
    ctx = SharedContext()
    with patch(
        "zrb.llm.prompt.manager.get_prompt",
        side_effect=lambda name, **kw: f"# {name}",
    ):
        composed = manager.compose_prompt()(ctx)
    assert "# Live Status" in composed


def test_registered_section_follows_include_order():
    """A registered section appears at its configured position, not last."""
    manager = PromptManager(include_sections=["persona", "live_status", "mandate"])
    manager.register_section("live_status", lambda ctx: "# Live Status")
    ctx = SharedContext()
    with patch(
        "zrb.llm.prompt.manager.get_prompt",
        side_effect=lambda name, **kw: (
            "# Identity" if name == "persona" else "# Operating Rules"
        ),
    ):
        composed = manager.compose_prompt()(ctx)
    assert (
        composed.index("# Identity")
        < composed.index("# Live Status")
        < composed.index("# Operating Rules")
    )


def test_registered_section_takes_precedence_over_markdown_file():
    """A registered provider shadows a same-named markdown file."""
    manager = PromptManager(include_sections=["live_status"])
    manager.register_section("live_status", lambda ctx: "# From Provider")
    ctx = SharedContext()
    with patch(
        "zrb.llm.prompt.manager.get_prompt",
        side_effect=lambda name, **kw: "# From File",
    ):
        composed = manager.compose_prompt()(ctx)
    assert "# From Provider" in composed
    assert "# From File" not in composed


def test_registered_section_receives_context():
    """The provider is invoked with the active context."""
    seen = {}

    def provider(ctx):
        seen["ctx"] = ctx
        return "# Dynamic"

    manager = PromptManager(include_sections=["live_status"])
    manager.register_section("live_status", provider)
    ctx = SharedContext()
    with patch("zrb.llm.prompt.manager.get_prompt", return_value=""):
        manager.compose_prompt()(ctx)
    assert seen["ctx"] is ctx


def test_register_section_overwrites_previous_provider():
    """Re-registering the same name replaces the earlier provider."""
    manager = PromptManager(include_sections=["live_status"])
    manager.register_section("live_status", lambda ctx: "# First")
    manager.register_section("live_status", lambda ctx: "# Second")
    ctx = SharedContext()
    with patch("zrb.llm.prompt.manager.get_prompt", return_value=""):
        composed = manager.compose_prompt()(ctx)
    assert "# Second" in composed
    assert "# First" not in composed


def test_builtin_section_not_shadowed_by_registered_provider():
    """A provider registered under a built-in name never shadows the built-in."""
    manager = PromptManager(include_sections=["mandate"])
    manager.register_section("mandate", lambda ctx: "# Hijacked")
    ctx = SharedContext()
    with patch(
        "zrb.llm.prompt.manager.get_prompt",
        side_effect=lambda name, **kw: f"# Builtin {name}",
    ):
        composed = manager.compose_prompt()(ctx)
    assert "# Builtin mandate" in composed
    assert "# Hijacked" not in composed


# ── Tool guidance ─────────────────────────────────────────────────────────────


def _guidance_manager(**extra) -> PromptManager:
    """Helper: a PromptManager with tool_guidance enabled."""
    return PromptManager(
        include_sections=["tool_guidance"],
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
