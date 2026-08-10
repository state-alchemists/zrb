import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager, new_prompt
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.prompt.section_filter import filter_requires


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


def test_prompt_manager_workflow_section_is_the_whole_rulebook():
    """`workflow` owns everything the retired mandate/git_mandate carried."""
    manager = PromptManager(include_sections=["workflow"], skill_manager=None)

    composed = manager.compose_prompt()(SharedContext())

    assert "## Priority Order" in composed
    assert "## Working Loop" in composed
    assert "## Verify Before Done" in composed
    assert "## Skill Activation" in composed
    assert "## Tool usage" in composed


def test_prompt_manager_retired_section_composes_to_nothing():
    """A pinned config naming a deleted section degrades, it does not crash."""
    manager = PromptManager(
        include_sections=["mandate", "git_mandate", "tool_guidance"],
        skill_manager=None,
    )

    assert manager.compose_prompt()(SharedContext()).strip() == ""


def test_prompt_manager_registered_provider_wins_over_file():
    """Overriding a section means supplying your own content."""
    manager = PromptManager(include_sections=["workflow"], skill_manager=None)
    manager.register_section("workflow", lambda ctx: "# Mine")

    composed = manager.compose_prompt()(SharedContext())

    assert "# Mine" in composed
    assert "## Working Loop" not in composed


def test_prompt_manager_mandate_alone_when_workflow_listed_elsewhere():
    """With `workflow` listed, `mandate` emits only its own content."""
    manager = PromptManager(
        include_sections=["mandate", "persona", "workflow"], skill_manager=None
    )

    composed = manager.compose_prompt()(SharedContext())

    # Both present, but Working Loop must appear exactly once (no duplication).
    assert composed.count("## Working Loop") == 1
    assert composed.count("## Priority Order") == 1


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
    manager.append_prompt("P1")
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


@pytest.mark.asyncio
async def test_create_live_context_async_matches_sync_shape():
    """The async twin (per-turn hot path, git off-loop) renders the same block
    shape and honors custom providers, with ContextVar wiring on the loop."""
    manager = PromptManager(include_sections=[])
    manager.add_live_context("test_provider", lambda ctx: "- Custom: hello")
    ctx = MagicMock()
    ctx.input.session = "live-ctx-async-test"

    with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
        mock_tm.get_todos.return_value = None
        rendered = await manager.create_live_context_async(ctx)

    assert rendered.startswith("<live-context>")
    assert rendered.rstrip().endswith("</live-context>")
    assert "Time:" in rendered
    assert "Custom: hello" in rendered

    from zrb.llm.tool.ambient_state import get_current_tool_session

    # The wiring side effect must land in the caller's context, not a thread's.
    assert get_current_tool_session() == "live-ctx-async-test"


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
    coupled to that section (ADR-0042): it is emitted only when journal_mandate
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


def test_live_context_journal_index_follows_the_journal_flag():
    """With journaling off the index is suppressed even when callers ask for it.

    There is no journal prompt section to couple to any more, so the flag is
    checked in render_journal_index itself.
    """
    with patch("zrb.llm.prompt.live_context.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_ENABLED = False
        rendered = _render_with_journal(
            inject_journal_index=True, index_body="# My Journal Hub"
        )
    assert "<journal-index>" not in rendered
    assert "My Journal Hub" not in rendered


def test_compose_minimal_uses_variant():
    """ZRB_LLM_PROFILE=minimal selects the .minimal variant where one exists."""
    manager = PromptManager(include_sections=["persona"])
    manager.model = "anthropic:claude-opus-4-8"
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "minimal"}):
        prompt = manager.compose_prompt()(SharedContext())
    assert (
        filter_requires(
            get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb"),
            set(manager.active_sections),
        )
        in prompt
    )


def test_compose_minimal_resolves_the_minimal_variant():
    """`minimal` composes persona.minimal.md, not the base file."""
    manager = PromptManager(include_sections=["persona"])
    manager.model = "anthropic:claude-opus-4-8"
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "minimal"}):
        prompt = manager.compose_prompt()(SharedContext())
    # The variant file, minus the blocks referencing sections this config omits.
    variant = get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb")
    assert filter_requires(variant, {"persona"}) in prompt
    assert get_prompt("persona", ASSISTANT_NAME="Zrb") not in prompt


def test_compose_drops_a_block_referencing_an_omitted_section():
    """workflow's project-doc pointer must not survive without project_context."""
    with_ctx = PromptManager(include_sections=["workflow", "project_context"])
    without = PromptManager(include_sections=["workflow"])
    ctx = SharedContext()
    assert "Documentation Files Found" in with_ctx.compose_prompt()(ctx)
    assert "Documentation Files Found" not in without.compose_prompt()(ctx)


def test_compose_auto_uses_the_full_base_for_a_model_declaring_no_small_size():
    """A family name is never read as weakness — only a stated size is (ADR-0049)."""
    manager = PromptManager(include_sections=["persona"])
    manager.model = (
        "deepseek:deepseek-v4-pro"  # a frontier model; must not be guessed weak
    )
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "auto"}):
        prompt = manager.compose_prompt()(SharedContext())
    assert (
        filter_requires(
            get_prompt("persona", ASSISTANT_NAME="Zrb"), set(manager.active_sections)
        )
        in prompt
    )
    assert (
        filter_requires(
            get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb"),
            set(manager.active_sections),
        )
        not in prompt
    )


def test_compose_auto_selects_minimal_from_a_declared_small_size():
    """A stated ≤4B count ships the minimal variant without any config."""
    manager = PromptManager(include_sections=["persona"])
    manager.model = "ollama:qwen2.5:3b"
    with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "auto"}):
        prompt = manager.compose_prompt()(SharedContext())
    assert (
        filter_requires(
            get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb"),
            set(manager.active_sections),
        )
        in prompt
    )


def test_compose_auto_honors_declared_model_profile():
    """A declared per-model mapping drives auto resolution through compose."""
    from zrb.llm.prompt.profile import model_profile_registry, register_model_profile

    manager = PromptManager(include_sections=["persona"])
    manager.model = "ollama:my-small-3b"
    register_model_profile("my-small-3b", "minimal")
    try:
        with patch.dict(os.environ, {"ZRB_LLM_PROFILE": "auto"}):
            prompt = manager.compose_prompt()(SharedContext())
    finally:
        model_profile_registry.clear()
    assert (
        filter_requires(
            get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb"),
            set(manager.active_sections),
        )
        in prompt
    )


def test_minimal_supplies_the_section_list_it_binds(monkeypatch):
    """`minimal` is the only preset that constrains the section axis (ADR-0049)."""
    from zrb.llm.prompt.profile import MINIMAL_SECTIONS

    manager = PromptManager()
    monkeypatch.setenv("ZRB_LLM_PROFILE", "minimal")
    assert manager.active_sections == list(MINIMAL_SECTIONS)
    monkeypatch.setenv("ZRB_LLM_PROFILE", "full")
    assert manager.active_sections == list(CFG.LLM_INCLUDE_SECTIONS)


def test_an_env_section_list_outranks_the_preset(monkeypatch):
    """A user who names sections has named them, whatever the preset would bind."""
    monkeypatch.setenv("ZRB_LLM_PROFILE", "minimal")
    monkeypatch.setenv("ZRB_LLM_INCLUDE_SECTIONS", "persona,examples")
    assert PromptManager().active_sections == ["persona", "examples"]


def test_a_changed_default_does_not_outrank_the_preset(monkeypatch):
    """Overriding the *default* in zrb_init.py changes a fallback, not a choice.

    Only the env var counts as naming a list — a preset outranking a default is
    the intended precedence, and the two are indistinguishable from the value
    alone, which is why this reads `CFG.is_env_set` rather than comparing.
    """
    from zrb.llm.prompt.profile import MINIMAL_SECTIONS

    monkeypatch.setenv("ZRB_LLM_PROFILE", "minimal")
    monkeypatch.delenv("ZRB_LLM_INCLUDE_SECTIONS", raising=False)
    monkeypatch.setattr(CFG, "DEFAULT_LLM_INCLUDE_SECTIONS", "persona,examples")
    assert PromptManager().active_sections == list(MINIMAL_SECTIONS)


def test_an_instance_section_list_outranks_the_preset(monkeypatch):
    """The constructor argument is the most local statement of intent."""
    monkeypatch.setenv("ZRB_LLM_PROFILE", "minimal")
    manager = PromptManager(include_sections=["workflow"])
    assert manager.active_sections == ["workflow"]


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
        include_sections=["workflow", "persona"],
    )
    ctx = SharedContext()
    composed = manager.compose_prompt()(ctx)
    # "workflow" starts with "# Operating Rules", "persona" with "# Identity"
    workflow_pos = composed.index("# Operating Rules")
    persona_pos = composed.index("# Identity")
    assert workflow_pos < persona_pos

    # Reverse order
    manager2 = PromptManager(
        include_sections=["persona", "workflow"],
    )
    composed2 = manager2.compose_prompt()(ctx)
    persona_pos2 = composed2.index("# Identity")
    workflow_pos2 = composed2.index("# Operating Rules")
    assert persona_pos2 < workflow_pos2


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


def test_active_sections_falls_back_to_cfg_default():
    """When include_sections is unset, active_sections uses the CFG default."""
    manager = PromptManager()  # include_sections is None
    assert manager.active_sections == list(CFG.LLM_INCLUDE_SECTIONS)


def test_active_sections_is_not_filtered_by_the_journal_flag():
    """Journaling no longer owns a section, so the flag must not touch this list.

    It gates the journal *tools* at registration instead; filtering here as well
    would silently drop a user's custom section named after the old one.
    """
    manager = PromptManager(include_sections=["persona", "workflow"])
    with patch("zrb.llm.prompt.manager.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = False
        assert manager.active_sections == ["persona", "workflow"]


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


def test_retired_section_name_still_serves_a_user_override():
    """A retired name plus a markdown override keeps working as a custom section.

    Users who overrode `mandate.md` and pinned it in ZRB_LLM_INCLUDE_SECTIONS
    should not silently lose their customization: the name falls through to the
    file-backed custom-section path and their file is emitted at that position.
    The upgrading guide documents exactly this, so it is pinned here.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        prompt_dir = os.path.join(temp_dir, ".zrb/llm/prompt")
        os.makedirs(prompt_dir)
        with open(os.path.join(prompt_dir, "mandate.md"), "w") as f:
            f.write("# My Old Mandate Override")

        env = {"ZRB_LLM_PROMPT_DIR": ".zrb/llm/prompt", "_ZRB_ENV_PREFIX": "ZRB"}
        with patch.dict(os.environ, env):
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                manager = PromptManager(
                    include_sections=["persona", "mandate"], skill_manager=None
                )
                composed = manager.compose_prompt()(SharedContext())
            finally:
                os.chdir(original_cwd)

    assert "My Old Mandate Override" in composed
    # Position is honoured: the override lands after persona, where it was listed.
    assert composed.index("# Identity") < composed.index("# My Old Mandate Override")
