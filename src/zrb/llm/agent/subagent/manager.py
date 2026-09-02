from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from zrb.context.any_context import AnyContext
from zrb.llm.agent.subagent.building import SubAgentBuilding
from zrb.llm.agent.subagent.definition import SubAgentDefinition
from zrb.llm.agent.subagent.manager_loading import SubAgentManagerLoading
from zrb.llm.agent.subagent.manager_search import SubAgentManagerSearch
from zrb.llm.agent.subagent.registry import SubAgentRegistry, sub_agent_registry
from zrb.llm.agent.subagent.tool_resolver import resolved_tool_name
from zrb.llm.common_tools import apply_common_tools
from zrb.util.asset_scanner import IGNORE_DIRS

if TYPE_CHECKING:
    from typing import Any

    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    from zrb.llm.task.chat.task import LLMChatTask


class SubAgentManager:
    def __init__(
        self,
        tool_registry: "dict[str, Callable | Tool] | None" = None,
        scan_root: str = ".",
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
        registry: SubAgentRegistry | None = None,
    ):
        # Lightweight: just assign properties, no heavy operations
        """Discover sub-agent definitions and build agents from them.

        Decomposed: the manager owns discovery (`scan`, `search_dirs`) and
        agent construction, and composes a `SubAgentRegistry` for the
        canonical definition collection. All definition query and mutation
        methods delegate to the registry, so a manual `add_agent`/`set_agents`
        survives a later scan.

        Args:
            tool_registry: Tools available to sub-agents, by name. Defaults to
                the shared common-tool registry.
            scan_root: Directory the project-level search starts from, and the
                recursive scan target.
            search_dirs: Explicit directories to scan, replacing the defaults
                derived from `scan_root`.
            max_depth: How many directory levels below each search directory to
                descend.
            ignore_dirs: Directory names skipped while scanning.
            registry: The canonical `SubAgentRegistry` of definitions to read
                and write. A fresh registry is created when `None`.
        """
        self._registry = registry if registry is not None else SubAgentRegistry()
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
        self._scan_root = scan_root
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._scanned_agents: dict[str, SubAgentDefinition] = {}
        self._ignore_dirs = IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._loaded: bool = False
        self._loading = SubAgentManagerLoading(
            ignore_dirs=self._ignore_dirs, agents=self._scanned_agents
        )
        self._search = SubAgentManagerSearch()
        self._building = SubAgentBuilding(self)

    @property
    def registry(self) -> SubAgentRegistry:
        """The canonical definition collection this manager reads and writes."""
        return self._registry

    @property
    def scan_root(self) -> str:
        """Directory the project-level search starts from, and the recursive
        scan target — not to be confused with `search_dirs`."""
        return self._scan_root

    @scan_root.setter
    def scan_root(self, value: str) -> None:
        self._scan_root = value

    def reload(self):
        """Force re-scan agents. Use after CFG changes or agent file updates.

        Manual registrations survive; only the discovered layer is refreshed.
        """
        self._loaded = False
        self._registry.clear_discovered()
        self._ensure_loaded()

    @property
    def search_dirs(self) -> list[str | Path]:
        """Directories scanned for sub-agent definitions, in priority order.

        The explicit override passed at construction (or set here), or the
        computed defaults when none was given. See
        `SubAgentManagerSearch.get_search_directories` for the full order.
        """
        if self._search_dirs is not None:
            return list(self._search_dirs)
        return self._search.get_search_directories(self._scan_root)

    @search_dirs.setter
    def search_dirs(self, value: list[str | Path] | None) -> None:
        self._search_dirs = value
        self._loaded = False

    def append_tool(self, *tool: "Callable | Tool"):
        """Append tools."""
        for single_tool in tool:
            tool_name = resolved_tool_name(single_tool) or str(single_tool)
            self._tool_registry[tool_name] = single_tool

    def append_tool_factory(
        self,
        *factory: (
            "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]"
        ),
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
        """Scan default and provided directories. Doesn't clear manual registrations.

        Manually-registered definitions are kept; a manual registration wins a
        name collision with a discovered one.
        """
        target_search_dirs = (
            search_dirs if search_dirs is not None else self.search_dirs
        )
        self._scanned_agents.clear()
        for search_dir in target_search_dirs:
            self._loading.scan_dir(
                Path(search_dir), max_depth=self._max_depth, root_dir=self._scan_root
            )
        self._registry.set_discovered(list(self._scanned_agents.values()))
        self._loaded = True
        return self.get_agents()

    def add_agent(self, definition: SubAgentDefinition):
        """Manually register a sub-agent definition. Survives a later scan."""
        self._registry.add_agent(definition)

    def remove_agent(self, name: str) -> None:
        """Drop a sub-agent definition by name (manual and discovered)."""
        self._ensure_loaded()
        self._registry.remove_agent(name)

    def set_agents(self, agents):
        """Replace the whole definition collection with *agents*.

        *agents* may be a list of `SubAgentDefinition` or a deferred callable
        returning one. Like `add_agent`, this registration survives a later scan.
        """
        self._registry.set_agents(agents)

    def get_agents(self) -> list[SubAgentDefinition]:
        """Return all sub-agent definitions, loading lazily on first call."""
        self._ensure_loaded()
        return self._registry.get_agents()

    def get_agent_definition(self, name: str) -> SubAgentDefinition | None:
        """Look up a sub-agent definition, loading them first if needed.

        Matches the registry key, then falls back to matching an agent's own
        name or path. Returns None when nothing matches.
        """
        self._ensure_loaded()
        return self._registry.get_agent_definition(name)

    @property
    def tool_registry_overrides(self) -> "dict[str, Callable | Tool]":
        """Tools registered via `append_tool`, before merging with the shared
        `tool_registry` — read by `SubAgentBuilding.get_tool_registry`."""
        return self._tool_registry

    @property
    def tool_factory_overrides(
        self,
    ) -> "list[Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]]":
        """Tool factories registered via `append_tool_factory`."""
        return self._tool_factories

    @property
    def toolset_overrides(self) -> "list[AbstractToolset[None]]":
        """Toolsets registered via `append_toolset`."""
        return self._toolsets

    @property
    def toolset_factory_overrides(
        self,
    ) -> "list[Callable[[AnyContext], AbstractToolset[None]]]":
        """Toolset factories registered via `append_toolset_factory`."""
        return self._toolset_factories

    def create_agent(
        self, name: str, ctx: AnyContext | None = None, yolo: bool | None = None
    ) -> "Agent[None, Any] | None":
        """Build a ready-to-run pydantic-ai agent from a sub-agent definition.

        See `SubAgentBuilding.create_agent`.
        """
        return self._building.create_agent(name, ctx, yolo)

    def create_llm_chat_task(
        self, name: str, ctx: AnyContext | None = None
    ) -> "LLMChatTask | None":
        """Build an `LLMChatTask` driven by this sub-agent's persona.

        See `SubAgentBuilding.create_llm_chat_task`.
        """
        return self._building.create_llm_chat_task(name, ctx)

    def resolve_agent_build(
        self,
        definition: SubAgentDefinition,
        ctx: AnyContext | None,
        yolo: bool | None,
    ):
        """Shared resolution logic behind `create_agent`/`create_llm_chat_task`.

        See `SubAgentBuilding.resolve_agent_build`. Public — the CLI TUI's
        persona-swap-on-`/load` (Item 4, Phase D) calls it directly, outside
        this module, to mutate a running task's persona in place.
        """
        return self._building.resolve_agent_build(definition, ctx, yolo)

    def _ensure_loaded(self):
        """Lazy load agents on first access. No-op if already loaded."""
        if not self._loaded:
            self._scan_and_load()
            self._loaded = True

    def _scan_and_load(self):
        """Internal: scan filesystem and load agents without resetting existing ones."""
        self._scanned_agents.clear()
        for search_dir in self.search_dirs:
            self._loading.scan_dir(
                Path(search_dir), max_depth=self._max_depth, root_dir=self._scan_root
            )
        self._registry.set_discovered(list(self._scanned_agents.values()))

    def get_tool_registry(self) -> "dict[str, Callable | Tool]":
        """Static tools keyed by name, including the shared zrb tools.

        See `SubAgentBuilding.get_tool_registry`.
        """
        return self._building.get_tool_registry()

    def get_tool_factories(
        self,
    ) -> "list[Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]]":
        """Config-gated tool factories (journal, plan-mode, skill, ...).

        See `SubAgentBuilding.get_tool_factories`.
        """
        return self._building.get_tool_factories()

    def get_all_toolsets(self, ctx: AnyContext) -> "list[AbstractToolset[None]]":
        """All toolsets including those resolved from factories.

        See `SubAgentBuilding.get_all_toolsets`.
        """
        return self._building.get_all_toolsets(ctx)


# Module-level singleton - lightweight, agents loaded on first access
sub_agent_manager = SubAgentManager(registry=sub_agent_registry)

# Give the singleton the shared zrb-shipped tool surface. The provider appends
# are pure storage; nothing resolves (and the transitively-imported
# `pydantic_ai` does not load) until the first agent build.
apply_common_tools(sub_agent_manager)
