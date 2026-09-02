"""Builds a runnable sub-agent from a roster entry — the construction half
of `SubAgentManager`, split out so the manager itself stays a roster
resolver (ADR-0090: registry/manager shape, not registry-plus-factory).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.agent.common import create_agent
from zrb.llm.agent.subagent.definition import SubAgentDefinition
from zrb.llm.agent.subagent.tool_resolver import (
    canonical_tool_name,
    resolve_tools_by_name,
    resolved_tool_name,
)
from zrb.llm.agent.subagent.yolo import make_yolo_inheritance_checker
from zrb.llm.config.model_resolver import resolve_configured_model
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.prompt.live_context import render_journal_index
from zrb.llm.summarizer import create_summarizer_history_processor
from zrb.llm.tool.registry import tool_registry

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.agent.subagent.manager import SubAgentManager
    from zrb.llm.task.chat.task import LLMChatTask


@dataclass
class _ResolvedAgentBuild:
    """Shared build inputs for `create_agent`/`create_llm_chat_task`."""

    model: Any
    system_prompt: str
    tools: list
    toolsets: list
    yolo: "bool | Callable[..., bool]"


class SubAgentBuilding:
    """Builds a runnable sub-agent from a definition in the roster.

    Composed by `SubAgentManager`, which owns the roster; this part owns
    turning one entry of that roster into an agent or an `LLMChatTask`.
    """

    def __init__(self, owner: "SubAgentManager") -> None:
        self._owner = owner

    def create_agent(
        self, name: str, ctx: AnyContext | None = None, yolo: bool | None = None
    ) -> "Agent[None, Any] | None":
        """Build a ready-to-run pydantic-ai agent from a sub-agent definition.

        Args:
            name: Sub-agent to build, resolved as in `get_agent_definition`.
            ctx: Task context supplying the tools and prompt state the agent
                inherits.
            yolo: Override for whether the agent may skip tool confirmation.
                Defaults to inheriting the parent's setting.

        Returns:
            The agent, or None when `name` matches no definition.
        """
        definition = self._owner.get_agent_definition(name)
        if not definition:
            return None
        if definition.agent_instance:
            return definition.agent_instance
        if definition.agent_factory:
            try:
                return definition.agent_factory()
            except Exception as e:
                CFG.LOGGER.debug(f"Sub-agent factory '{name}' failed: {e}")

        resolved = self.resolve_agent_build(definition, ctx, yolo)

        # resolve_model=False: resolved.model was already resolved (so section
        # factories could use it). Re-resolving inside create_agent would
        # double-fire model_getter/model_renderer.
        return create_agent(
            model=resolved.model,
            system_prompt=resolved.system_prompt,
            tools=resolved.tools,
            toolsets=resolved.toolsets,
            history_processors=[create_summarizer_history_processor()],
            yolo=resolved.yolo,
            resolve_model=False,
        )

    def create_llm_chat_task(
        self, name: str, ctx: AnyContext | None = None
    ) -> "LLMChatTask | None":
        """Build an `LLMChatTask` driven by this sub-agent's persona.

        Same system prompt / tool / model resolution as `create_agent`, but
        wrapped in the zrb `Task` type the web chat runner needs (`.async_run`,
        `.history_manager`, `.ui_factories`, ...) instead of a bare pydantic-ai
        `Agent` — this is what lets a human resume/continue a delegated
        session driven by the actual sub-agent, not the main agent (Item 4,
        Phase C).

        A definition built from `agent_instance`/`agent_factory` (a pre-built
        pydantic-ai `Agent`, not a system_prompt/tools/model triple) has
        nothing to re-derive a task's config from, so this returns `None` for
        those — the minority case among sub-agent definitions.
        """
        definition = self._owner.get_agent_definition(name)
        if not definition or definition.agent_instance or definition.agent_factory:
            return None

        resolved = self.resolve_agent_build(definition, ctx, yolo=None)

        # lazy: zrb.llm.task.chat.task transitively loads pydantic_ai,
        # prompt_toolkit and the full chat-task machinery.
        from zrb.llm.task.chat.task import LLMChatTask

        return LLMChatTask(
            name=f"resumed-{definition.name}",
            description=definition.description,
            system_prompt=resolved.system_prompt,
            tools=resolved.tools,
            toolsets=resolved.toolsets,
            model=resolved.model,
            # resolved.model is already final (resolve_configured_model ran
            # above) — rendering it as a template would be wrong for a
            # non-string Model instance and is a no-op-at-best for a plain
            # model-id string, so skip it, mirroring create_agent's
            # resolve_model=False.
            render_model=False,
            history_processors=[create_summarizer_history_processor()],
            # These four mirror builtin/llm/chat.py's bindings exactly: the web
            # chat runner (chat_session_runner.py) drives any llm_chat_task via
            # a per-message SharedContext(input={...}), so the task must read
            # its message/session/attachments/interactivity from ctx.input
            # rather than from constructor defaults.
            message="{ctx.input.message}",
            conversation_name="{ctx.input.session}",
            attachment=lambda ctx: [
                path.strip() for path in ctx.input.attach.split(",") if path.strip()
            ],
            interactive="{ctx.input.interactive}",
        )

    def resolve_agent_build(
        self,
        definition: SubAgentDefinition,
        ctx: AnyContext | None,
        yolo: bool | None,
    ) -> "_ResolvedAgentBuild":
        """Shared resolution logic behind `create_agent`/`create_llm_chat_task`:
        tools (registry + factories, minus delegate tools and disallowed
        names), toolsets, resolved model, and the effective system prompt
        (inherited sections + the definition's own body). Public — the CLI
        TUI's persona-swap-on-`/load` (Item 4, Phase D) calls it directly,
        outside this module, to mutate a running task's persona in place."""
        if ctx is None:
            ctx = Context(
                shared_ctx=SharedContext(),
                task_name="sub-agent-task",
                color=0,
                icon="🤖",
            )

        resolved_tools = resolve_tools_by_name(
            definition.tools,
            self.get_tool_registry(),
            self._owner.tool_factory_overrides,
            ctx,
        )

        if definition.disallowed_tools:
            disallowed = {
                canonical_tool_name(name) for name in definition.disallowed_tools
            }
            resolved_tools = [
                t for t in resolved_tools if resolved_tool_name(t) not in disallowed
            ]

        resolved_toolsets = self.get_all_toolsets(ctx)

        # YOLO: an explicit True/False wins; None (or anything else) returns a
        # checker that reads the live parent state on each invocation (so
        # toggles propagate). The old truthiness-only check made an explicit
        # False indistinguishable from unset.
        effective_yolo: bool | Callable[..., bool]
        if yolo is True:
            effective_yolo = True
        elif yolo is False:
            effective_yolo = False
        else:
            effective_yolo = make_yolo_inheritance_checker()

        # Resolve model so section factories can use it
        final_model = resolve_configured_model(definition.model)

        # Inherited sections (persona, workflow, system_context, ...) come from
        # the main-agent PromptManager composition. Sub-agents that need the
        # parent's identity / operating rules / project context declare
        # ``inherit_sections`` in their frontmatter; an agent that omits it
        # (``inherit_sections = None``) keeps only its own prompt.
        inherited_prompt = self._build_inherited_prompt(
            ctx, definition.inherit_sections, final_model
        )

        parts: list[str] = []
        if inherited_prompt:
            parts.append(inherited_prompt)
        if definition.system_prompt:
            parts.append(definition.system_prompt)
        effective_system_prompt = "\n\n".join(parts).strip()

        return _ResolvedAgentBuild(
            model=final_model,
            system_prompt=effective_system_prompt,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            yolo=effective_yolo,
        )

    def _build_inherited_prompt(
        self,
        ctx: AnyContext,
        inherit_sections: "list[str] | None",
        model: Any,
    ) -> str:
        """Compose the named PromptManager sections for sub-agent inheritance.

        ``None`` → return ``""`` (no-inheritance sub-agent). ``[]`` → return
        ``""`` (explicit opt-out). A non-empty list builds a temporary
        PromptManager scoped to just those sections.

        """
        if not inherit_sections:
            return ""
        # lazy: zrb internal (heavy via transitive) — PromptManager pulls in
        # skill_manager which pulls in hook_manager; not a cycle, verified
        # empirically.
        from zrb.llm.prompt.manager import PromptManager

        sections = list(inherit_sections)
        pm = PromptManager(include_sections=sections)
        pm.model = model
        try:
            composed = pm.compose_prompt()(ctx).strip()
            # Sub-agents are single-turn (one run_agent, empty history), so the
            # cross-turn caching reason for keeping volatile state out of the
            # system prompt does not apply. Fold the <live-context> block back
            # into the inherited prompt so an agent that inherits system_context
            # still sees the per-turn state (time, git, …) it saw before the
            # main-chat split — the main chat injects it into the user turn
            # instead, via run_agent's live_context. Being single-turn, a
            # sub-agent is always "the first turn": inject the journal index
            # unconditionally (render_journal_index itself honours
            # LLM_JOURNAL_ENABLED). See ADR-0042.
            if "system_context" in sections:
                live = pm.create_live_context(ctx, inject_journal_index=True)
                if live:
                    composed = f"{composed}\n\n{live}".strip()
            else:
                # No system_context to carry it: inject the index alone, not the
                # per-turn state that system_context owns.
                journal_block = render_journal_index()
                if journal_block:
                    composed = f"{composed}\n\n{journal_block}".strip()
            return composed
        except Exception:
            # Don't fail agent creation on inheritance issues — surface as no
            # inheritance so the sub-agent still runs.
            return ""

    def get_tool_registry(self) -> "dict[str, Callable | Tool]":
        """Static tools keyed by name, including the shared zrb tools.

        The shared registry is resolved lazily on the first call, so the heavy
        tool imports still stay off ``import zrb``. Manually registered tools
        win name collisions with the shared set.
        """
        registry = dict(self._owner.tool_registry_overrides)
        for tool in tool_registry.get_tools():
            name = resolved_tool_name(tool)
            if name is not None:
                registry.setdefault(name, tool)
        return registry

    def get_tool_factories(
        self,
    ) -> "list[Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]]":
        """Config-gated tool factories (journal, plan-mode, skill, ...). Public
        for the same reason as `get_tool_registry`."""
        return self._owner.tool_factory_overrides

    def get_all_toolsets(self, ctx: AnyContext) -> "list[AbstractToolset[None]]":
        """All toolsets including those resolved from factories."""
        return resolve_factory_items(
            self._owner.toolset_overrides, self._owner.toolset_factory_overrides, ctx
        )
