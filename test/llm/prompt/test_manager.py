import os
import tempfile
from unittest.mock import MagicMock, patch

from zrb.config.config import CFG
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


def test_create_live_context_wraps_volatile_state_in_tags():
    """create_live_context returns the per-turn block wrapped as <live-context>."""
    manager = PromptManager(include_sections=[])
    ctx = MagicMock()
    ctx.input.session = "live-ctx-test"

    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = manager.create_live_context(ctx)

    assert rendered.startswith("<live-context>")
    assert rendered.rstrip().endswith("</live-context>")
    # Volatile content lives here, not in the cached system prompt.
    assert "Time:" in rendered


def test_add_live_context_appends_custom_content():
    """Custom live context providers extend the <live-context> block."""
    manager = PromptManager(include_sections=[])
    manager.add_live_context("test_provider", lambda ctx: "- Custom: hello")

    ctx = MagicMock()
    ctx.input.session = "add-live-ctx-test"

    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = manager.create_live_context(ctx)

    assert "Custom: hello" in rendered


def test_add_live_context_overwrites_same_name():
    """Re-registering the same name replaces the previous provider."""
    manager = PromptManager(include_sections=[])
    manager.add_live_context("dup", lambda ctx: "- First")
    manager.add_live_context("dup", lambda ctx: "- Second")

    ctx = MagicMock()
    ctx.input.session = "overwrite-test"

    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = manager.create_live_context(ctx)

    assert "Second" in rendered
    assert "First" not in rendered


def test_add_live_context_handles_none_return():
    """A provider returning None/empty string is safely skipped."""
    manager = PromptManager(include_sections=[])
    manager.add_live_context("skip", lambda ctx: None)
    manager.add_live_context("also_skip", lambda ctx: "")

    ctx = MagicMock()
    ctx.input.session = "none-test"

    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = manager.create_live_context(ctx)

    assert "Time:" in rendered


def _render_with_journal(
    inject_journal_index: bool,
    index_body: str,
    sections: list[str] | None = None,
) -> str:
    """Render live-context with a temp journal index, returning the block.

    *sections* defaults to ``["journal_mandate"]`` because the journal index is
    coupled to that section (ADR-0082): it is emitted only when journal_mandate
    is active. Pass ``[]`` to exercise the suppression path.
    """
    manager = PromptManager(
        include_sections=["journal_mandate"] if sections is None else sections
    )
    ctx = MagicMock()
    ctx.input.session = "journal-test"
    with tempfile.TemporaryDirectory() as journal_dir:
        with open(os.path.join(journal_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write(index_body)
        env = {
            "ZRB_LLM_JOURNAL_DIR": journal_dir,
            "ZRB_LLM_JOURNAL_INDEX_FILE": "index.md",
        }
        with (
            patch.dict(os.environ, env),
            patch("zrb.llm.tool.plan.todo_manager") as mock_tm,
        ):
            mock_tm.get_todos.return_value = None
            return manager.create_live_context(
                ctx, inject_journal_index=inject_journal_index
            )


def test_live_context_includes_journal_index_when_requested():
    """The journal index snapshot is injected when inject_journal_index is set."""
    rendered = _render_with_journal(
        inject_journal_index=True, index_body="# My Journal Hub"
    )
    assert "<journal-index>" in rendered
    assert "</journal-index>" in rendered
    assert "My Journal Hub" in rendered


def test_live_context_omits_journal_index_by_default():
    """Without the flag the index is omitted — it is already present in history."""
    rendered = _render_with_journal(
        inject_journal_index=False, index_body="# My Journal Hub"
    )
    assert "My Journal Hub" not in rendered
    assert "<journal-index>" not in rendered
    # The volatile per-turn lines still render.
    assert "Time:" in rendered


def test_live_context_skips_empty_journal_index():
    """An empty index file produces no journal block even when requested."""
    rendered = _render_with_journal(inject_journal_index=True, index_body="   \n")
    assert "<journal-index>" not in rendered


def test_live_context_couples_journal_index_to_journal_mandate_section():
    """Even with the flag set, the index is suppressed when journal_mandate is
    not an active section — the index is coupled to that section (ADR-0082)."""
    rendered = _render_with_journal(
        inject_journal_index=True, index_body="# My Journal Hub", sections=[]
    )
    assert "<journal-index>" not in rendered
    assert "My Journal Hub" not in rendered
    # The volatile per-turn lines still render.
    assert "Time:" in rendered


def test_compose_explicit_register_uses_variant():
    """ZRB_LLM_PROFILE=explicit selects the explicit phrasing variant."""
    manager = PromptManager(include_sections=["persona"])
    manager.model = "anthropic:claude-opus-4-8"
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "explicit"}):
        prompt = manager.compose_prompt()(SharedContext())
    assert "No preamble" in prompt  # explicit persona variant


def test_compose_explicit_includes_examples_section_when_listed():
    """When examples is in include_sections, profile=explicit resolves examples.explicit.md."""
    manager = PromptManager(include_sections=["persona", "examples"])
    manager.model = "anthropic:claude-opus-4-8"
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "explicit"}):
        prompt = manager.compose_prompt()(SharedContext())
    assert "No preamble" in prompt  # explicit persona variant
    assert "Worked Examples" in prompt  # examples section (explicit variant)


def test_compose_auto_defaults_to_terse_base():
    """auto makes no capability guess — terse base, no examples — for any model."""
    manager = PromptManager(include_sections=["persona"])
    manager.model = (
        "deepseek:deepseek-v4-pro"  # a frontier model; must not be guessed weak
    )
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "auto"}):
        prompt = manager.compose_prompt()(SharedContext())
    assert "Match depth and format" in prompt  # base persona
    assert "Worked Examples" not in prompt  # no examples under terse


def test_compose_auto_honors_declared_model_profile():
    """A declared per-model mapping drives auto resolution through compose."""
    from zrb.llm.prompt.profile import model_profile_registry, register_model_profile

    manager = PromptManager(include_sections=["persona", "examples"])
    manager.model = "ollama:my-small-3b"
    register_model_profile("my-small-3b", "explicit")
    try:
        with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "auto"}):
            prompt = manager.compose_prompt()(SharedContext())
    finally:
        model_profile_registry.clear()
    assert "No preamble" in prompt
    assert "Worked Examples" in prompt


def test_add_live_context_swallows_provider_exceptions():
    """A broken provider is isolated: it neither crashes the block nor leaks."""
    manager = PromptManager(include_sections=[])

    def broken(_ctx):
        raise RuntimeError("boom")

    manager.add_live_context("broken", broken)

    ctx = MagicMock()
    ctx.input.session = "exception-test"

    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = manager.create_live_context(ctx)

    # Built-in content still renders
    assert "Time:" in rendered
    # Broken provider is silently skipped
    assert "boom" not in rendered


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


def test_builtin_section_can_be_overridden_by_registered_provider():
    """A registered provider takes precedence over an identically-named built-in."""
    manager = PromptManager(include_sections=["mandate"])
    manager.register_section("mandate", lambda ctx: "# Overridden")
    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    assert "# Overridden" in composed


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


# ── tool_names property ───────────────────────────────────────────────────────


def test_tool_names_property_get_and_set():
    """`tool_names` round-trips through its getter/setter."""
    manager = PromptManager(tool_names={"A", "B"})
    assert manager.tool_names == {"A", "B"}
    manager.tool_names = {"C"}
    assert manager.tool_names == {"C"}


def test_active_sections_falls_back_to_cfg_default():
    """When include_sections is unset, active_sections uses the CFG default."""
    manager = PromptManager()  # include_sections is None
    assert manager.active_sections == list(CFG.LLM_INCLUDE_SECTIONS)


def test_tool_guidance_sections_property_round_trips():
    """`tool_guidance_sections` round-trips and normalizes falsy input to []."""
    manager = PromptManager()
    assert manager.tool_guidance_sections == []
    manager.tool_guidance_sections = ["## Block"]
    assert manager.tool_guidance_sections == ["## Block"]
    manager.tool_guidance_sections = None
    assert manager.tool_guidance_sections == []


# ── Live context edge cases ───────────────────────────────────────────────────


def test_create_live_context_returns_empty_when_no_content():
    """With nothing to report the block collapses to an empty string."""
    manager = PromptManager(include_sections=[])
    ctx = MagicMock()
    ctx.input.session = "empty-live"
    with patch("zrb.llm.prompt.manager.render_live_context", return_value=""):
        rendered = manager.create_live_context(ctx)
    assert rendered == ""


# ── Custom system context providers ───────────────────────────────────────────


def _render_system_context(manager: PromptManager) -> str:
    """Compose the system_context section with the todo manager stubbed out."""
    ctx = MagicMock()
    ctx.input.session = "sys-ctx-test"
    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        return manager.compose_prompt()(ctx)


def test_add_system_context_provider_appears_and_overwrites():
    """Custom system-context providers extend the section; same name overwrites."""
    manager = PromptManager(include_sections=["system_context"])
    manager.add_system_context("extra", lambda ctx: "SYS-FIRST")
    manager.add_system_context("extra", lambda ctx: "SYS-SECOND")  # overwrite
    manager.add_system_context("more", lambda ctx: "SYS-MORE")  # append

    rendered = _render_system_context(manager)

    assert "SYS-SECOND" in rendered
    assert "SYS-FIRST" not in rendered
    assert "SYS-MORE" in rendered


def test_system_context_provider_exception_is_swallowed():
    """A broken system-context provider is isolated; built-in content survives."""
    manager = PromptManager(include_sections=["system_context"])

    def broken(_ctx):
        raise RuntimeError("sys-boom")

    manager.add_system_context("broken", broken)
    manager.model = "openai:gpt-4o"

    rendered = _render_system_context(manager)

    assert "sys-boom" not in rendered
    assert "openai:gpt-4o" in rendered  # built-in system context still renders


# ── Custom project context providers ──────────────────────────────────────────


def test_add_project_context_provider_appears_and_overwrites():
    """Custom project-context providers extend the section; same name overwrites."""
    manager = PromptManager(include_sections=["project_context"])
    manager.add_project_context("extra", lambda ctx: "PROJ-FIRST")
    manager.add_project_context("extra", lambda ctx: "PROJ-SECOND")  # overwrite
    manager.add_project_context("more", lambda ctx: "PROJ-MORE")  # append

    ctx = SharedContext()
    rendered = manager.compose_prompt()(ctx)

    assert "Custom Project Context" in rendered
    assert "PROJ-SECOND" in rendered
    assert "PROJ-FIRST" not in rendered
    assert "PROJ-MORE" in rendered


def test_project_context_provider_exception_is_swallowed():
    """A broken project-context provider is isolated and emits nothing."""
    manager = PromptManager(include_sections=["project_context"])

    def broken(_ctx):
        raise RuntimeError("proj-boom")

    manager.add_project_context("broken", broken)

    ctx = SharedContext()
    rendered = manager.compose_prompt()(ctx)

    assert "proj-boom" not in rendered


# ── Section skipping ──────────────────────────────────────────────────────────


def test_git_mandate_section_skipped_outside_git_dir():
    """git_mandate is dropped when the process is not inside a git repo."""
    manager = PromptManager(include_sections=["git_mandate"])
    ctx = SharedContext()
    with patch("zrb.llm.prompt.manager.is_inside_git_dir", return_value=False):
        rendered = manager.compose_prompt()(ctx)
    assert rendered.strip() == ""


def test_claude_skills_section_is_silently_skipped():
    """The retired claude_skills section is skipped without a warning section."""
    manager = PromptManager(include_sections=["claude_skills"])
    ctx = SharedContext()
    rendered = manager.compose_prompt()(ctx)
    assert rendered.strip() == ""


# ── File-backed section warnings ──────────────────────────────────────────────


def test_missing_section_uses_ctx_log_warning_when_available():
    """A missing file-backed section warns via ctx.log_warning when callable."""
    manager = PromptManager(include_sections=["nope_section"])
    ctx = MagicMock()
    ctx.log_warning = MagicMock()
    with patch("zrb.llm.prompt.manager.get_prompt", return_value=""):
        manager.compose_prompt()(ctx)
    assert ctx.log_warning.called


# ── Non-standard prompt inputs ────────────────────────────────────────────────


def test_non_callable_non_string_prompt_is_rendered_as_content():
    """A non-callable, non-string prompt is coerced to string content."""
    manager = PromptManager(prompts=[123], include_sections=[])
    ctx = SharedContext()
    rendered = manager.compose_prompt()(ctx)
    assert "123" in rendered
