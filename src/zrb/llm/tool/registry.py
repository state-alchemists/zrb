"""The canonical tool registry.

``tool_registry`` holds the ordered static tools, per-run tool factories and
toolset factories zrb agents start from. Its default is a lazy seed (the
built-ins import ``pydantic_ai``), resolved on first read; any mutation
materializes the seed first.
"""

from __future__ import annotations

from typing import Any, Callable, TypeAlias

from zrb.config.config import CFG

#: Static tool: a plain function or a pydantic-ai ``Tool`` wrapping one.
ToolLike: TypeAlias = Callable | Any
#: Per-run factory: resolves one tool or a list of tools from the context.
ToolFactory: TypeAlias = Callable[[Any], Any]
#: Per-run toolset factory: resolves a toolset (or list of them) from context.
ToolsetFactory: TypeAlias = Callable[[Any], Any]
#: The three ordered lists a registry contributes to a host.
ToolSeed: TypeAlias = tuple[list, list, list]


def tool_name(tool: ToolLike | Any) -> str:
    """Registered name of *tool*, whether it is a bare function or a ``Tool``."""
    fn = getattr(tool, "function", tool)
    return getattr(fn, "__name__", "") or getattr(tool, "name", "") or ""


class ToolRegistry:
    """The ordered set of tools and factories for zrb agents."""

    def __init__(self, default: Callable[[], ToolSeed] | None = None) -> None:
        """default: optional lazy seed returning ``(tools, tool_factories, toolset_factories)``."""
        self._seed = default
        self._tools: list[ToolLike] = []
        self._tool_factories: list[ToolFactory] = []
        self._toolset_factories: list[ToolsetFactory] = []
        self._materialized = False

    def _resolved(self) -> ToolSeed:
        """Materialize the lazy seed once, returning the three lists."""
        if not self._materialized:
            if self._seed is not None:
                tools, factories, toolsets = self._seed()
                self._tools = list(tools)
                self._tool_factories = list(factories)
                self._toolset_factories = list(toolsets)
            self._materialized = True
        return (
            list(self._tools),
            list(self._tool_factories),
            list(self._toolset_factories),
        )

    def _configured_names(self) -> list[str]:
        """The ``LLM_TOOLS`` name allowlist, or ``[]`` meaning "all"."""
        return list(CFG.LLM_TOOLS or [])

    def get_tools(self) -> list[ToolLike]:
        """The resolved static tools, in order, filtered by ``CFG.LLM_TOOLS``."""
        tools, _, _ = self._resolved()
        allowed = self._configured_names()
        if allowed:
            tools = [t for t in tools if tool_name(t) in allowed]
        return tools

    def get_tool_factories(self) -> list[ToolFactory]:
        """The resolved per-run tool factories, in order."""
        _, factories, _ = self._resolved()
        return list(factories)

    def get_toolset_factories(self) -> list[ToolsetFactory]:
        """The resolved per-run toolset factories, in order."""
        _, _, toolsets = self._resolved()
        return list(toolsets)

    def append_tool(self, *tool: ToolLike) -> None:
        """Append *tool* after everything currently registered (runs last)."""
        self._resolved()
        self._tools.extend(tool)

    def prepend_tool(self, *tool: ToolLike) -> None:
        """Prepend *tool* before everything currently registered (runs first)."""
        self._resolved()
        self._tools[0:0] = tool

    def set_tools(self, tools: list[ToolLike]) -> None:
        """Replace the static tool list wholesale; factories/toolsets kept."""
        self._resolved()
        self._tools = list(tools)

    def remove_tool(self, tool: ToolLike | str) -> None:
        """Drop every static tool matching *tool* by identity or registered name."""
        tools, _, _ = self._resolved()
        name = tool if isinstance(tool, str) else tool_name(tool)
        self._tools = [t for t in tools if not (t is tool or tool_name(t) == name)]

    def append_tool_factory(self, *factory: ToolFactory) -> None:
        """Append a per-run tool factory."""
        self._resolved()
        self._tool_factories.extend(factory)

    def prepend_tool_factory(self, *factory: ToolFactory) -> None:
        """Prepend a per-run tool factory."""
        self._resolved()
        self._tool_factories[0:0] = factory

    def set_tool_factories(self, factories: list[ToolFactory]) -> None:
        """Replace the per-run tool-factory list wholesale."""
        self._resolved()
        self._tool_factories = list(factories)

    def remove_tool_factory(self, factory: ToolFactory) -> None:
        """Drop a per-run tool factory by identity."""
        self._resolved()
        self._tool_factories = [f for f in self._tool_factories if f is not factory]

    def append_toolset_factory(self, *factory: ToolsetFactory) -> None:
        """Append a per-run toolset factory."""
        self._resolved()
        self._toolset_factories.extend(factory)

    def prepend_toolset_factory(self, *factory: ToolsetFactory) -> None:
        """Prepend a per-run toolset factory."""
        self._resolved()
        self._toolset_factories[0:0] = factory

    def set_toolset_factories(self, factories: list[ToolsetFactory]) -> None:
        """Replace the per-run toolset-factory list wholesale."""
        self._resolved()
        self._toolset_factories = list(factories)

    def remove_toolset_factory(self, factory: ToolsetFactory) -> None:
        """Drop a per-run toolset factory by identity."""
        self._resolved()
        self._toolset_factories = [
            f for f in self._toolset_factories if f is not factory
        ]

    def set_seed(self, seed: Callable[[], ToolSeed]) -> None:
        """Install *seed* as the lazy default, unless already materialized."""
        if not self._materialized:
            self._seed = seed

    def apply_to(self, host) -> None:
        """Append every tool, factory and toolset factory to a ``CommonToolHost``."""
        host.append_tool(*self.get_tools())
        host.append_tool_factory(*self.get_tool_factories())
        host.append_toolset_factory(*self.get_toolset_factories())


#: The shared registry; its seed is wired in ``zrb.llm.common_tools``.
tool_registry = ToolRegistry()
