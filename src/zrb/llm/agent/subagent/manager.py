from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.agent.common import create_agent
from zrb.llm.agent.subagent.manager_loading import SubAgentManagerLoading
from zrb.llm.agent.subagent.manager_search import SubAgentManagerSearch
from zrb.llm.agent.subagent.tool_resolver import (
    canonical_tool_name,
    resolve_tools_by_name,
    resolved_tool_name,
)
from zrb.llm.agent.subagent.yolo import make_yolo_inheritance_checker
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.prompt.live_context import render_journal_index
from zrb.llm.summarizer import create_summarizer_history_processor
from zrb.util.asset_scanner import IGNORE_DIRS

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.task.chat.task import LLMChatTask


@dataclass
class _ResolvedAgentBuild:
    """Shared build inputs for `create_agent`/`create_llm_chat_task`."""

    model: Any
    system_prompt: str
    tools: list
    toolsets: list
    yolo: "bool | Callable[..., bool]"


class SubAgentDefinition:
    """A delegatable sub-agent, as loaded from a `*.agent.md` file or built in code.

    Register one with `sub_agent_manager.add_agent(SubAgentDefinition(...))`;
    `DelegateToAgent` then lists it and can hand it work.
    """

    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        system_prompt: str,
        model: str | None = None,
        tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        agent_instance: Any | None = None,
        agent_factory: Callable[[], Any] | None = None,
        inherit_sections: list[str] | None = None,
    ):
        """Define a sub-agent.

        Args:
            name: How the agent is addressed when delegating to it.
            path: Directory the definition was loaded from; relative paths in
                `system_prompt` resolve against it.
            description: What this agent is for. `DelegateToAgent` shows this to
                the delegating model, so it decides whether work is routed here.
            system_prompt: The agent's own operating instructions.
            model: Model override. Defaults to the delegating task's model.
            tools: Tool names the agent may call. Empty means the default
                surface. A Claude-authored definition listing `Bash` maps onto
                zrb's `Shell` as it loads.
            disallowed_tools: Tool names to subtract from whatever `tools`
                resolved to.
            agent_instance: A pre-built pydantic-ai agent to use instead of
                constructing one from the fields above.
            agent_factory: Callable returning that agent, for construction that
                must happen per run.
            inherit_sections: Prompt sections copied from the delegating task.
                None inherits the default set.
        """
        self.name = name
        self.path = path
        self.description = description
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools if tools is not None else []
        self.disallowed_tools = disallowed_tools if disallowed_tools is not None else []
        self.agent_instance = agent_instance
        self.agent_factory = agent_factory
        # Inherit named PromptManager sections from the main-agent composition
        # (persona, workflow, examples, system_context, project_context).
        # None = no inheritance (only the body + tool guidance).
        # Use ``[]`` to explicitly opt out while documenting the intent.
        self.inherit_sections = inherit_sections


class SubAgentManager:
    def __init__(
        self,
        tool_registry: "dict[str, Callable | Tool] | None" = None,
        root_dir: str = ".",
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        # Lightweight: just assign properties, no heavy operations
        """Discover sub-agent definitions and build agents from them.

        Args:
            tool_registry: Tools available to sub-agents, by name. Defaults to
                the shared common-tool registry.
            root_dir: Directory the project-level search starts from.
            search_dirs: Explicit directories to scan, replacing the defaults
                derived from `root_dir`.
            max_depth: How many directory levels below each search directory to
                descend.
            ignore_dirs: Directory names skipped while scanning.
        """
        self._tool_registry = tool_registry if tool_registry is not None else {}
        self._tool_factories: list[
            Callable[
                [AnyContext],
                Tool | ToolFuncEither | list[Tool | ToolFuncEither],
            ]
        ] = []
        self._toolsets: list[AbstractToolset[None]] = []
        self._toolset_factories: list[Callable[[AnyContext], AbstractToolset[None]]] = (
            []
        )
        self._root_dir = root_dir
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._agents: dict[str, SubAgentDefinition] = {}
        self._ignore_dirs = IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._loaded: bool = False
        self._loading = SubAgentManagerLoading(
            ignore_dirs=self._ignore_dirs, agents=self._agents
        )
        self._search = SubAgentManagerSearch()

    @property
    def root_dir(self) -> str:
        """Directory the project-level search starts from."""
        return self._root_dir

    @root_dir.setter
    def root_dir(self, value: str) -> None:
        self._root_dir = value

    def reload(self):
        """Force re-scan agents. Use after CFG changes or agent file updates."""
        self._loaded = False
        # Cleared in place (not reassigned): `self._loading` holds a reference
        # to this same dict, which a reassignment would orphan.
        self._agents.clear()
        self._ensure_loaded()

    def get_search_directories(self) -> list[str | Path]:
        """All agent search directories in priority order. See
        `SubAgentManagerSearch.get_search_directories` for the full order."""
        return self._search.get_search_directories(self._root_dir)

    def append_tool(self, *tool: "Callable | Tool"):
        """Append tools."""
        for single_tool in tool:
            tool_name = resolved_tool_name(single_tool) or str(single_tool)
            self._tool_registry[tool_name] = single_tool

    def append_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ):
        """Append tool factories."""
        for single_factory in factory:
            self._tool_factories.append(single_factory)

    def append_toolset(self, *toolset: AbstractToolset[None]):
        """Append toolsets."""
        self._toolsets += list(toolset)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """Append toolset factories."""
        self._toolset_factories += list(factory)

    def scan(
        self, search_dirs: list[str | Path] | None = None
    ) -> list[SubAgentDefinition]:
        """Scan default and provided directories. Doesn't clear manual registrations."""
        target_search_dirs = search_dirs
        if target_search_dirs is None:
            target_search_dirs = (
                self._search_dirs
                if self._search_dirs is not None
                else self.get_search_directories()
            )
        for search_dir in target_search_dirs:
            self._loading.scan_dir(
                Path(search_dir), max_depth=self._max_depth, root_dir=self._root_dir
            )
        self._loaded = True
        return list(self._agents.values())

    def add_agent(self, definition: SubAgentDefinition):
        """Manually register a sub-agent definition."""
        self._agents[definition.name] = definition

    def get_agent_definition(self, name: str) -> SubAgentDefinition | None:
        """Look up a sub-agent definition, loading them first if needed.

        Matches the registry key, then falls back to matching an agent's own
        name or path. Returns None when nothing matches.
        """
        self._ensure_loaded()
        agent = self._agents.get(name)
        if not agent:
            for a in self._agents.values():
                if a.name == name or a.path == name:
                    agent = a
                    break
        return agent

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
        # lazy: circular — common_tools imports back into this package.
        from zrb.llm.common_tools import ensure_common_tools

        ensure_common_tools(self)
        definition = self.get_agent_definition(name)
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
        definition = self.get_agent_definition(name)
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
            # resolved.model is already final (default_llm_config.resolve_model
            # ran above) — rendering it as a template would be wrong for a
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

        registry = self.get_tool_registry()
        resolved_tools = resolve_tools_by_name(definition.tools, registry)

        for factory in self._tool_factories:
            tool = factory(ctx)
            if isinstance(tool, list):
                for single_tool in tool:
                    if not getattr(single_tool, "zrb_is_delegate_tool", False):
                        resolved_tools.append(single_tool)
            elif not getattr(tool, "zrb_is_delegate_tool", False):
                resolved_tools.append(tool)

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
        final_model = default_llm_config.resolve_model(definition.model)

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
        # lazy: zrb internal (heavy via transitive / circular) — PromptManager
        # pulls in skill_manager which pulls in hook_manager.
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

    def _ensure_loaded(self):
        """Lazy load agents on first access. No-op if already loaded."""
        if not self._loaded:
            self._scan_and_load()
            self._loaded = True

    def _scan_and_load(self):
        """Internal: scan filesystem and load agents without resetting existing ones."""
        target_search_dirs = self._search_dirs
        if target_search_dirs is None:
            target_search_dirs = self.get_search_directories()
        for search_dir in target_search_dirs:
            self._loading.scan_dir(
                Path(search_dir), max_depth=self._max_depth, root_dir=self._root_dir
            )

    def get_tool_registry(self) -> "dict[str, Callable | Tool]":
        """Statically-registered tools, keyed by name. Public — hook/creator.py's
        agent-hook tool resolution reads this from outside the class."""
        return self._tool_registry

    def get_tool_factories(
        self,
    ) -> "list[Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]]":
        """Config-gated tool factories (journal, plan-mode, skill, ...). Public
        for the same reason as `get_tool_registry`."""
        return self._tool_factories

    def get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """All toolsets including those resolved from factories."""
        return resolve_factory_items(self._toolsets, self._toolset_factories, ctx)


# Module-level singleton - lightweight, agents loaded on first access
sub_agent_manager = SubAgentManager()


# Imported here (after SubAgentManager is defined) to break a circular import:
# common_tools's registration functions pull in zrb.llm.tool, whose __init__
# loads delegate.py, which imports SubAgentManager from this module.
# Importing at the top would hit this module mid-load before the class exists.

from zrb.llm.common_tools import defer_common_tools

# Deferred (not applied now): applying pulls in pydantic_ai via the tool
# imports. ``create_agent`` calls ``ensure_common_tools(self)`` before it reads
# the tool surface, so the heavy import lands on the first agent build instead
# of on ``import zrb``.
defer_common_tools(sub_agent_manager)
