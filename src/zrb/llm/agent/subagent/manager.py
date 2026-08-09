from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.agent.common import create_agent
from zrb.llm.agent.subagent.manager_loading import SubAgentManagerLoading
from zrb.llm.agent.subagent.manager_search import SubAgentManagerSearch
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


# Claude Code names its shell tool ``Bash``; zrb ships a single ``Shell`` tool.
# A sub-agent file written for Claude that lists ``Bash`` maps onto ``Shell``,
# so an agent's `tools:` / `disallowedTools:` frontmatter keeps working
# unmodified (case-insensitive, e.g. ``Bash`` or ``bash``).
_TOOL_NAME_ALIASES = {"bash": "Shell"}


def _canonical_tool_name(name: str) -> str:
    """The zrb tool name that implements the Claude-compatible name *name*."""
    return _TOOL_NAME_ALIASES.get(name.lower(), name)


def _resolve_tool_name(t: Any) -> str | None:
    raw = getattr(t, "name", None)
    if raw is not None:
        return raw
    return getattr(t, "__name__", None)


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


class SubAgentManager(SubAgentManagerLoading, SubAgentManagerSearch):
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
        self._tool_factories: list[Callable[[AnyContext], Tool | ToolFuncEither]] = []
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

    def reload(self):
        """Force re-scan agents. Use after CFG changes or agent file updates."""
        self._loaded = False
        self._agents = {}
        self._ensure_loaded()

    def append_tool(self, *tool: "Callable | Tool"):
        """Append tools."""
        for single_tool in tool:
            tool_name = _resolve_tool_name(single_tool) or str(single_tool)
            self._tool_registry[tool_name] = single_tool

    def append_tool_factory(
        self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]
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
            self._scan_dir(Path(search_dir), max_depth=self._max_depth)
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

        if ctx is None:

            ctx = Context(
                shared_ctx=SharedContext(),
                task_name="sub-agent-task",
                color=0,
                icon="🤖",
            )

        resolved_tools = []
        registry = self._get_tool_registry()
        for tool_name in definition.tools:
            tool = registry.get(_canonical_tool_name(tool_name))
            if tool is not None and not getattr(tool, "zrb_is_delegate_tool", False):
                resolved_tools.append(tool)

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
                _canonical_tool_name(name) for name in definition.disallowed_tools
            }
            resolved_tools = [
                t for t in resolved_tools if _resolve_tool_name(t) not in disallowed
            ]

        resolved_toolsets = self.get_all_toolsets(ctx)

        # YOLO: explicit True wins; otherwise return a checker that reads the
        # live parent state on each invocation (so toggles propagate).
        effective_yolo: bool | Callable[..., bool]
        if yolo is True:
            effective_yolo = True
        else:
            effective_yolo = make_yolo_inheritance_checker()

        # Resolve model so section factories can use it
        final_model = default_llm_config.resolve_model(definition.model)

        # Inherited sections (persona, workflow, system_context, ...) come from
        # the main-agent PromptManager composition. Sub-agents that need the
        # parent's identity / operating rules / project context declare
        # ``inherit_sections`` in their frontmatter; an agent that omits it
        # (``inherit_sections = None``) stays lean.
        inherited_prompt = self._build_inherited_prompt(
            ctx, definition.inherit_sections, final_model
        )

        parts: list[str] = []
        if inherited_prompt:
            parts.append(inherited_prompt)
        if definition.system_prompt:
            parts.append(definition.system_prompt)
        effective_system_prompt = "\n\n".join(parts).strip()

        # resolve_model=False: definition.model was already resolved into
        # final_model above (so section factories could use it). Re-resolving
        # inside create_agent would double-fire model_getter/model_renderer.
        return create_agent(
            model=final_model,
            system_prompt=effective_system_prompt,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            history_processors=[create_summarizer_history_processor()],
            yolo=effective_yolo,
            resolve_model=False,
        )

    def _build_inherited_prompt(
        self,
        ctx: AnyContext,
        inherit_sections: "list[str] | None",
        model: Any,
    ) -> str:
        """Compose the named PromptManager sections for sub-agent inheritance.

        ``None`` → return ``""`` (lean sub-agent). ``[]`` → return
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
            self._scan_dir(Path(search_dir), max_depth=self._max_depth)

    def _get_tool_registry(self) -> "dict[str, Callable | Tool]":
        return self._tool_registry

    def get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """All toolsets including those resolved from factories."""
        return resolve_factory_items(self._toolsets, self._toolset_factories, ctx)


# Module-level singleton - lightweight, agents loaded on first access
sub_agent_manager = SubAgentManager()


# Imported here (after SubAgentManager is defined) to break a circular import:
# default_tools pulls in zrb.llm.tool, whose __init__ loads delegate.py, which
# imports SubAgentManager from this module. Importing at the top would hit
# this module mid-load before the class exists.

from zrb.llm.common_tools import defer_common_tools

# Deferred (not applied now): applying pulls in pydantic_ai via the tool
# imports. ``create_agent`` calls ``ensure_common_tools(self)`` before it reads
# the tool surface, so the heavy import lands on the first agent build instead
# of on ``import zrb``.
defer_common_tools(sub_agent_manager)
