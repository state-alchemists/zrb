from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import AnyContext
from zrb.llm.agent.common import create_agent
from zrb.llm.agent.subagent.loader_mixin import LoaderMixin
from zrb.llm.agent.subagent.search_mixin import SearchMixin
from zrb.llm.agent.subagent.yolo import make_yolo_inheritance_checker
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.summarizer import (
    create_summarizer_history_processor,
)

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

_IGNORE_DIRS = [
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    "dist",
    "build",
    "htmlcov",
]


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
    ):
        self.name = name
        self.path = path
        self.description = description
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools
        self.agent_instance = agent_instance
        self.agent_factory = agent_factory


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
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._loaded: bool = False  # Track if agents have been loaded

    def _ensure_loaded(self):
        """Lazy load agents on first access. No-op if already loaded."""
        if not self._loaded:
            self._scan_and_load()
            self._loaded = True

    def reload(self):
        """Force re-scan agents. Use after CFG changes or agent file updates."""
        self._loaded = False
        self._agents = {}
        self._ensure_loaded()

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
        all_toolsets = list(self._toolsets)
        for factory in self._toolset_factories:
            toolset = factory(ctx)
            if isinstance(toolset, list):
                all_toolsets.extend(toolset)
            else:
                all_toolsets.append(toolset)
        return all_toolsets

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
            from zrb.context.context import Context
            from zrb.context.shared_context import SharedContext

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

        final_model = default_llm_config.resolve_model(definition.model)
        return create_agent(
            model=final_model,
            system_prompt=definition.system_prompt,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            history_processors=[
                create_summarizer_history_processor(
                    model_getter=default_llm_config.model_getter,
                    model_renderer=default_llm_config.model_renderer,
                )
            ],
            yolo=effective_yolo,
        )


# Module-level singleton - lightweight, agents loaded on first access
sub_agent_manager = SubAgentManager()

# Register the zrb-shipped tools. Lives in a sibling module so the visible
# tool surface stays in one place.
from zrb.llm.agent.subagent.default_tools import register_default_tools  # noqa: E402

register_default_tools(sub_agent_manager)
