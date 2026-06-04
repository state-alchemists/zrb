from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.agent.common import create_agent
from zrb.llm.agent.subagent.manager.loader_mixin import LoaderMixin
from zrb.llm.agent.subagent.manager.search_mixin import SearchMixin
from zrb.llm.agent.subagent.yolo import make_yolo_inheritance_checker
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.prompt.tool_guidance import (
    ToolCatalogue,
    ToolGroups,
    ToolGuidance,
    get_tool_guidance_prompt,
)
from zrb.llm.summarizer import (
    create_summarizer_history_processor,
)
from zrb.util.asset_scanner import IGNORE_DIRS

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset


class SubAgentDefinition:
    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        system_prompt: str,
        model: str | None = None,
        tools: list[str] = [],
        agent_instance: Any | None = None,
        agent_factory: Callable[[], Any] | None = None,
        inherit_sections: list[str] | None = None,
    ):
        self.name = name
        self.path = path
        self.description = description
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools
        self.agent_instance = agent_instance
        self.agent_factory = agent_factory
        # Inherit named PromptManager sections from the main-agent composition
        # (persona, mandate, git_mandate, system_context, project_context, ...).
        # None = no inheritance (legacy behavior: only the body + tool guidance).
        # Use ``[]`` to explicitly opt out while documenting the intent.
        self.inherit_sections = inherit_sections


class SubAgentManager(LoaderMixin, SearchMixin):
    def __init__(
        self,
        tool_registry: dict[str, Callable] | None = None,
        root_dir: str = ".",
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        # Lightweight: just assign properties, no heavy operations
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
        self._loaded: bool = False  # Track if agents have been loaded
        self._tool_guidance: ToolCatalogue = {}
        self._tool_groups: ToolGroups = []
        # Guidance factories for dynamically-named tools (e.g., RunZrbTask).
        self._tool_guidance_factories: list[Callable[[AnyContext], ToolGuidance]] = []
        # Section factories for model-aware Tool Usage Guide intros (e.g., parallel-tool-call policy).
        self._tool_guidance_section_factories: list[
            Callable[[AnyContext, Any], str | None]
        ] = []

    def reload(self):
        """Force re-scan agents. Use after CFG changes or agent file updates."""
        self._loaded = False
        self._agents = {}
        self._ensure_loaded()

    def add_tool(self, *tool: Callable):
        """Register tools."""
        self.append_tool(*tool)

    def append_tool(self, *tool: Callable):
        """Append tools."""
        for single_tool in tool:
            tool_name = getattr(single_tool, "__name__", str(single_tool))
            self._tool_registry[tool_name] = single_tool

    def add_tool_factory(self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]):
        """Register tool factories."""
        self.append_tool_factory(*factory)

    def append_tool_factory(
        self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]
    ):
        """Append tool factories."""
        for single_factory in factory:
            self._tool_factories.append(single_factory)

    def add_toolset(self, *toolset: AbstractToolset[None]):
        """Register toolsets."""
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: AbstractToolset[None]):
        """Append toolsets."""
        self._toolsets += list(toolset)

    def add_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """Register toolset factories."""
        self.append_toolset_factory(*factory)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """Append toolset factories."""
        self._toolset_factories += list(factory)

    def add_tool_group(self, *, name: str) -> None:
        for label, _ in self._tool_groups:
            if label == name:
                return
        self._tool_groups.append((name, []))

    def add_tool_guidance(self, *guidances: ToolGuidance) -> None:
        for g in guidances:
            self.add_tool_group(name=g.group_name)
            self._tool_guidance[g.tool_name] = (g.when_to_use, g.key_rule)
            for label, members in self._tool_groups:
                if label == g.group_name:
                    if g.tool_name not in members:
                        members.append(g.tool_name)
                    break

    def add_tool_guidance_factory(
        self, *factory: "Callable[[AnyContext], ToolGuidance]"
    ):
        """Register guidance for dynamically-named factory tools.

        Each factory is called when creating an agent. It should return
        a single ToolGuidance object.
        """
        self._tool_guidance_factories.extend(factory)

    def add_tool_guidance_section_factory(
        self, *factory: "Callable[[AnyContext, Any], str | None]"
    ):
        """Register a factory that renders a model-aware Tool Usage Guide section.

        Each factory is called per-agent with ``(ctx, resolved_model)`` and
        returns a Markdown block (typically starting with ``## Heading``) or
        ``None``/empty string to skip injection.
        """
        self._tool_guidance_section_factories.extend(factory)

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
            self._scan_dir(search_dir, max_depth=self._max_depth)
        self._loaded = True
        return list(self._agents.values())

    def add_agent(self, definition: SubAgentDefinition):
        """Manually register a sub-agent definition."""
        self._agents[definition.name] = definition

    def set_tool_registry(self, tool_registry: dict[str, Callable]):
        """Update the tool registry used by sub-agents."""
        self._tool_registry = tool_registry

    def get_agent_definition(self, name: str) -> SubAgentDefinition | None:
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
        definition = self.get_agent_definition(name)
        if not definition:
            return None
        if definition.agent_instance:
            return definition.agent_instance
        if definition.agent_factory:
            try:
                return definition.agent_factory()
            except Exception:
                pass

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
            if tool_name in registry:
                tool = registry[tool_name]
                if not getattr(tool, "zrb_is_delegate_tool", False):
                    resolved_tools.append(tool)

        for factory in self._tool_factories:
            tool = factory(ctx)
            if isinstance(tool, list):
                for single_tool in tool:
                    if not getattr(single_tool, "zrb_is_delegate_tool", False):
                        resolved_tools.append(single_tool)
            elif not getattr(tool, "zrb_is_delegate_tool", False):
                resolved_tools.append(tool)

        resolved_toolsets = self._get_all_toolsets(ctx)

        # YOLO: explicit True wins; otherwise return a checker that reads the
        # live parent state on each invocation (so toggles propagate).
        effective_yolo: bool | Callable
        if yolo is True:
            effective_yolo = True
        else:
            effective_yolo = make_yolo_inheritance_checker()

        # Resolve model so section factories can use it
        final_model = default_llm_config.resolve_model(definition.model)

        # Resolve guidance factories for dynamically-named tools
        for factory in self._tool_guidance_factories:
            guidance = factory(ctx)
            self.add_tool_guidance(guidance)

        # Resolve section factories for model-aware guidance sections
        section_strings: list[str] = []
        for factory in self._tool_guidance_section_factories:
            rendered = factory(ctx, final_model)
            if rendered:
                section_strings.append(rendered)

        # Filter guidance to the sub-agent's resolved tool surface so we don't
        # emit guidance for tools it cannot call (notably the main-agent-only
        # delegate tools, which were stripped above via ``zrb_is_delegate_tool``).
        resolved_tool_names: set[str] = set()
        for t in resolved_tools:
            tname = getattr(t, "name", None) or getattr(t, "__name__", None)
            if tname:
                resolved_tool_names.add(tname)
        guidance_prompt = get_tool_guidance_prompt(
            resolved_tool_names or None,
            self._tool_guidance,
            self._tool_groups,
            extra_sections=section_strings if section_strings else None,
        )

        # Inherited sections (persona, mandate, system_context, ...) come from
        # the main-agent PromptManager composition. Sub-agents that need the
        # parent's identity / operating rules / project context declare
        # ``inherit_sections`` in their frontmatter; legacy agents with
        # ``inherit_sections = None`` keep the lean original behavior.
        inherited_prompt = self._build_inherited_prompt(
            ctx, definition.inherit_sections, final_model
        )

        parts: list[str] = []
        if inherited_prompt:
            parts.append(inherited_prompt)
        if definition.system_prompt:
            parts.append(definition.system_prompt)
        if guidance_prompt:
            parts.append(guidance_prompt)
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

        ``None`` → return ``""`` (legacy lean sub-agent). ``[]`` → return
        ``""`` (explicit opt-out). A non-empty list builds a temporary
        PromptManager scoped to just those sections.

        ``tool_guidance`` is intentionally NOT delegated to this PromptManager
        — the calling ``create_agent`` already composes the sub-agent's own
        tool-filtered guidance block, so re-rendering it here would either
        duplicate or use the wrong tool set.
        """
        if not inherit_sections:
            return ""
        # lazy: zrb internal (heavy via transitive / circular) — PromptManager
        # pulls in skill_manager which pulls in hook_manager.
        from zrb.llm.prompt.manager import PromptManager

        sections = [s for s in inherit_sections if s != "tool_guidance"]
        if not sections:
            return ""
        pm = PromptManager(include_sections=sections)
        pm.model = model
        # Sub-agents have a different tool subset; let inherited tool_guidance
        # (if any) render unfiltered rather than against the parent's tools.
        pm.tool_names = None
        try:
            return pm.compose_prompt()(ctx).strip()
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
            self._scan_dir(search_dir, max_depth=self._max_depth)

    def _get_tool_registry(self) -> dict[str, Callable]:
        return self._tool_registry

    def _get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """All toolsets including those resolved from factories."""
        return resolve_factory_items(self._toolsets, self._toolset_factories, ctx)


# Module-level singleton - lightweight, agents loaded on first access
sub_agent_manager = SubAgentManager()


# Imported here (after SubAgentManager is defined) to break a circular import:
# default_tools pulls in zrb.llm.tool, whose __init__ loads delegate.py, which
# imports SubAgentManager from this module. Importing at the top would hit
# this module mid-load before the class exists.

from zrb.llm.common_tools import apply_common_tools

apply_common_tools(sub_agent_manager)
