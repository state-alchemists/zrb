"""Builds a runnable sub-agent from a roster entry — the construction half
of `SubAgentManager`, split out so the manager itself stays a roster
resolver, not a roster-plus-factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.capabilities.prompt.live_context.context import render_carried_context
from zrb.llm.capabilities.tool_call.batch_nudge import create_batch_nudge_processor
from zrb.llm.contracts.config.model_resolver import resolve_configured_model
from zrb.llm.contracts.shared.ambient_state import get_current_tool_session
from zrb.llm.contracts.shared.factory_resolver import resolve_factory_items
from zrb.llm.contracts.shared.sub_agent_build import SubAgentBuild
from zrb.llm.contracts.shared.tool_registry import tool_registry
from zrb.llm.contracts.shared.tool_resolver import (
    canonical_tool_name,
    resolve_tools_by_name,
    resolved_tool_name,
)
from zrb.llm.engine.agent.common import create_agent
from zrb.llm.engine.agent.run.tool_capabilities import (
    build_capability_map,
    register_tool_capabilities,
)
from zrb.llm.engine.summarizer import create_summarizer_history_processor
from zrb.llm.orchestration.resumed_session import create_resumed_chat_task
from zrb.llm.orchestration.subagent.definition import SubAgentDefinition
from zrb.llm.orchestration.subagent.parent_message import send_message_to_parent
from zrb.llm.orchestration.subagent.yolo import make_yolo_inheritance_checker

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.orchestration.subagent.manager.manager import SubAgentManager
    from zrb.llm.orchestration.task.chat.task import LLMChatTask


def _subagent_archive_name(name: str) -> "Callable[[], str | None]":
    """The archive key of a sub-agent run, resolved when compaction runs.

    Keyed by the delegation it belongs to, so a resumed roster entry is a new
    conversation. With no delegation in scope there is nothing to tell two runs
    apart, so the name is left to the summarizer's opening-message key rather
    than making every run of `name` append to one file.
    """

    def resolve() -> str | None:
        session = get_current_tool_session()
        return f"subagent-{session}-{name}" if session else None

    return resolve


def _has_fallback_configuration(definition: SubAgentDefinition) -> bool:
    """Whether *definition* can build a usable agent without its factory.

    A Python `get_agent` factory's definition often has an empty
    `system_prompt` because the factory supplies the agent, but it may still
    declare `tools` or `inherit_sections` that the fallback agent would use.
    Only a definition with none of the three has nothing to fall back to.
    """
    return bool(
        definition.system_prompt.strip()
        or definition.tools
        or definition.inherit_sections
    )


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
                if not _has_fallback_configuration(definition):
                    # Nothing but the factory can build this definition: no
                    # prompt, no tools, no inherited sections. Falling through
                    # would build an agent with no instructions and no tools,
                    # turning a transient factory failure into confident,
                    # broken delegation. Report it instead.
                    raise RuntimeError(
                        f"Sub-agent '{name}' could not be built: its agent "
                        f"factory failed: {e}"
                    ) from e
                # A definition with a prompt, declared tools or inherited
                # sections keeps them as a fallback when the factory, an
                # override, fails.
                CFG.LOGGER.debug(f"Sub-agent factory '{name}' failed: {e}")

        resolved = self.resolve_agent_build(definition, ctx, yolo)

        # The inheritance checker reads the ambient map by name, and the cascade
        # reads it again after a call is deferred, so the tools this agent is
        # built with are registered before it is built — everything actually
        # supplied, `send_message_to_parent` included. A sub-agent built here
        # used to register nothing: a delegated `Edit` read as UNKNOWN, an
        # `edit:ask` rule missed it, and a later `*:allow` answered.
        tools = [*resolved.tools, send_message_to_parent]
        register_tool_capabilities(build_capability_map(tools))

        # resolve_model=False: resolved.model was already resolved (so section
        # factories could use it). Re-resolving inside create_agent would
        # double-fire model_getter/model_renderer.
        return create_agent(
            model=resolved.model,
            system_prompt=resolved.system_prompt,
            tools=tools,
            toolsets=resolved.toolsets,
            history_processors=[
                create_summarizer_history_processor(
                    # Resolved per request and per delegation: two runs of the
                    # same sub-agent are different conversations and must not
                    # share an archive. No session to name means no name at
                    # all, so the archive is keyed by the opening message
                    # instead of every run sharing one.
                    session_name=_subagent_archive_name(name)
                ),
                # A delegated run spends the same tokens on a serial streak as
                # the parent does, so it gets the same reminder.
                create_batch_nudge_processor(),
            ],
            yolo=resolved.yolo,
            resolve_model=False,
        )

    def create_llm_chat_task(
        self, name: str, ctx: AnyContext | None = None
    ) -> "LLMChatTask | None":
        """Build an ``LLMChatTask`` from a prompt-based sub-agent definition.

        Returns ``None`` for definitions supplied as a pre-built agent or
        factory, whose task configuration cannot be reconstructed.
        """
        definition = self._owner.get_agent_definition(name)
        if not definition or definition.agent_instance or definition.agent_factory:
            return None

        resolved = self.resolve_agent_build(definition, ctx, yolo=None)

        # `resumed_session.py` is the third unit of this layer: it names the
        # chat task, this package names it, and `task/` names neither back —
        # importing the task here would close the `subagent <-> task` cycle,
        # since the chat task reaches this manager for its roster and its
        # `@mentions`.
        return create_resumed_chat_task(
            resolved, definition.name, definition.description
        )

    def resolve_agent_build(
        self,
        definition: SubAgentDefinition,
        ctx: AnyContext | None,
        yolo: bool | None,
    ) -> "SubAgentBuild":
        """Resolve tools, toolsets, model, and system prompt for a definition."""
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
        # toggles propagate). Checked as `is True`/`is False`, not truthiness,
        # so an explicit False stays distinguishable from unset.
        effective_yolo: bool | Callable[..., bool]
        if yolo is True:
            effective_yolo = True
        elif yolo is False:
            effective_yolo = False
        else:
            effective_yolo = make_yolo_inheritance_checker()

        final_model = resolve_configured_model(definition.model)

        # Sections named in the agent's ``inherit_sections`` frontmatter come
        # from the main agent's PromptManager; without it, only its own prompt.
        inherited_prompt = self._build_inherited_prompt(
            ctx, definition.inherit_sections, final_model
        )

        parts: list[str] = []
        if inherited_prompt:
            parts.append(inherited_prompt)
        if definition.system_prompt:
            parts.append(definition.system_prompt)
        effective_system_prompt = "\n\n".join(parts).strip()

        return SubAgentBuild(
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
        PromptManager scoped to those sections.

        """
        if not inherit_sections:
            return ""
        # lazy: zrb internal (heavy via transitive) — PromptManager pulls in
        # skill_manager which pulls in hook_manager; not a cycle, verified
        # empirically.
        from zrb.llm.capabilities.prompt.manager import PromptManager

        sections = list(inherit_sections)
        pm = PromptManager(include_sections=sections)
        pm.model = model
        try:
            composed = pm.compose_prompt()(ctx).strip()
            # Sub-agents are single-turn, so prompt caching gives no reason to
            # keep volatile state out of the system prompt: fold <live-context>
            # and the memory block in here (the main chat puts them in the user
            # turn).
            if "system_context" in sections:
                live = pm.create_live_context(ctx, inject_memory=True)
                if live:
                    composed = f"{composed}\n\n{live}".strip()
            else:
                # No system_context to carry it: inject the memory block alone,
                # not the per-turn state that system_context owns.
                memory_block = render_carried_context()
                if memory_block:
                    composed = f"{composed}\n\n{memory_block}".strip()
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
        """Config-gated tool factories (memory, plan-mode, skill, ...). Public
        for the same reason as `get_tool_registry`."""
        return self._owner.tool_factory_overrides

    def get_all_toolsets(self, ctx: AnyContext) -> "list[AbstractToolset[None]]":
        """All toolsets including those resolved from factories."""
        return resolve_factory_items(
            self._owner.toolset_overrides, self._owner.toolset_factory_overrides, ctx
        )
