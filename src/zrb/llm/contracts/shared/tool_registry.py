"""The canonical tool registry.

``tool_registry`` holds the ordered static tools, per-run tool factories and
toolset factories zrb agents start from. Its default is a lazy seed (the
built-ins import ``pydantic_ai``), resolved on first read and before the first
mutation. A read that happens before a seed is installed does not close the
door: the seed is folded in front of whatever was registered in the meantime.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

from zrb.config.config import CFG
from zrb.llm.contracts.shared.tool_resolver import resolved_tool_name

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
        # What a caller did before the seed arrived. The built-ins are folded in
        # behind these, so an early registration is not undone by a late seed:
        # the three `_head_count`s were prepended ahead of it, `_removed` were
        # dropped by name or identity, and a replaced domain stays replaced.
        self._head_count = 0
        self._factory_head_count = 0
        self._toolset_head_count = 0
        self._removed: list[ToolLike | str] = []
        self._tools_replaced = False
        self._factories_replaced = False
        self._toolsets_replaced = False

    def _resolved(self) -> ToolSeed:
        """Materialize the lazy seed once, returning the three lists.

        Only a seed closes the door. A registry read before any seed exists
        returns nothing and stays open, so a caller that runs early — an agent
        hook fires outside any task run — cannot freeze the built-ins out of
        the process for every caller after it.

        Whatever was registered first keeps its meaning when the seed lands: a
        prepended tool stays ahead of the built-ins, an appended one behind
        them, a removed one removed, and a list replaced wholesale is not
        reopened by the built-ins.
        """
        if self._seed is not None and not self._materialized:
            tools, factories, toolsets = self._seed()
            if not self._tools_replaced:
                self._tools[self._head_count : self._head_count] = [
                    tool for tool in tools if not self._is_removed(tool)
                ]
            if not self._factories_replaced:
                self._tool_factories[
                    self._factory_head_count : self._factory_head_count
                ] = factories
            if not self._toolsets_replaced:
                self._toolset_factories[
                    self._toolset_head_count : self._toolset_head_count
                ] = toolsets
            self._materialized = True
        return (
            list(self._tools),
            list(self._tool_factories),
            list(self._toolset_factories),
        )

    def _is_removed(self, tool: ToolLike) -> bool:
        """Whether a `remove_tool` call already dropped *tool* by name or identity."""
        return any(
            tool is gone
            or (isinstance(gone, str) and tool_name(tool) == gone)
            or (not isinstance(gone, str) and tool_name(gone) == tool_name(tool))
            for gone in self._removed
        )

    def _head_after_removal(self, before: list, kept: list, head: int) -> int:
        """The prepend boundary once the dropped items are gone.

        Only an item *inside* the boundary shortens it: removing an appended
        one leaves it where it was. Taking the shorter list as the answer would
        let a removed prepend keep holding a place the seed then lands behind.
        """
        kept_ids = {id(item) for item in kept}
        return head - sum(1 for item in before[:head] if id(item) not in kept_ids)

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

    def tools_by_name(self) -> dict[str, ToolLike]:
        """The resolved static tools keyed by registered name; first wins.

        The map a name list is resolved against (`resolve_tools_by_name`). A
        host that layers its own registrations over the shared set copies this
        map first and fills its own names in, as `SubAgentBuilding` does.
        """
        named: dict[str, ToolLike] = {}
        for tool in self.get_tools():
            registered = resolved_tool_name(tool)
            if registered is not None:
                named.setdefault(registered, tool)
        return named

    def append_tool(self, *tool: ToolLike) -> None:
        """Append *tool* after everything currently registered (runs last)."""
        self._resolved()
        self._tools.extend(tool)

    def prepend_tool(self, *tool: ToolLike) -> None:
        """Prepend *tool* before everything currently registered (runs first)."""
        self._resolved()
        self._tools[0:0] = tool
        if not self._materialized:
            self._head_count += len(tool)

    def set_tools(self, tools: list[ToolLike]) -> None:
        """Replace the static tool list wholesale; factories/toolsets kept."""
        self._resolved()
        self._tools = list(tools)
        if not self._materialized:
            self._tools_replaced = True

    def remove_tool(self, tool: ToolLike | str) -> None:
        """Drop every static tool matching *tool* by identity or registered name."""
        tools, _, _ = self._resolved()
        name = tool if isinstance(tool, str) else tool_name(tool)
        self._tools = [t for t in tools if not (t is tool or tool_name(t) == name)]
        if not self._materialized:
            # The seed has not arrived, so the built-ins are not in the list
            # yet: remember the removal and apply it to them when they land.
            self._removed.append(tool)
            # A prepended tool that is now gone no longer sits ahead of the
            # seed.
            self._head_count = self._head_after_removal(
                tools, self._tools, self._head_count
            )

    def append_tool_factory(self, *factory: ToolFactory) -> None:
        """Append a per-run tool factory."""
        self._resolved()
        self._tool_factories.extend(factory)

    def prepend_tool_factory(self, *factory: ToolFactory) -> None:
        """Prepend a per-run tool factory."""
        self._resolved()
        self._tool_factories[0:0] = factory
        if not self._materialized:
            self._factory_head_count += len(factory)

    def set_tool_factories(self, factories: list[ToolFactory]) -> None:
        """Replace the per-run tool-factory list wholesale."""
        self._resolved()
        self._tool_factories = list(factories)
        if not self._materialized:
            self._factories_replaced = True

    def remove_tool_factory(self, factory: ToolFactory) -> None:
        """Drop a per-run tool factory by identity."""
        self._resolved()
        before = self._tool_factories
        self._tool_factories = [f for f in before if f is not factory]
        if not self._materialized:
            self._factory_head_count = self._head_after_removal(
                before, self._tool_factories, self._factory_head_count
            )

    def append_toolset_factory(self, *factory: ToolsetFactory) -> None:
        """Append a per-run toolset factory."""
        self._resolved()
        self._toolset_factories.extend(factory)

    def prepend_toolset_factory(self, *factory: ToolsetFactory) -> None:
        """Prepend a per-run toolset factory."""
        self._resolved()
        self._toolset_factories[0:0] = factory
        if not self._materialized:
            self._toolset_head_count += len(factory)

    def set_toolset_factories(self, factories: list[ToolsetFactory]) -> None:
        """Replace the per-run toolset-factory list wholesale."""
        self._resolved()
        self._toolset_factories = list(factories)
        if not self._materialized:
            self._toolsets_replaced = True

    def remove_toolset_factory(self, factory: ToolsetFactory) -> None:
        """Drop a per-run toolset factory by identity."""
        self._resolved()
        before = self._toolset_factories
        self._toolset_factories = [f for f in before if f is not factory]
        if not self._materialized:
            self._toolset_head_count = self._head_after_removal(
                before, self._toolset_factories, self._toolset_head_count
            )

    def set_seed(self, seed: Callable[[], ToolSeed]) -> None:
        """Install *seed* as the lazy default, unless one is already in use.

        A seed is refused once it has been folded in — replacing it then would
        drop the built-ins the process is already running with. A registry that
        was only read, or only mutated, before this call still takes one.
        """
        if not self._materialized:
            self._seed = seed

    def apply_to(self, host) -> None:
        """Append every tool, factory and toolset factory to a ``CommonToolHost``."""
        host.append_tool(*self.get_tools())
        host.append_tool_factory(*self.get_tool_factories())
        host.append_toolset_factory(*self.get_toolset_factories())


#: The shared registry; its seed is wired in ``zrb.llm.agent.tool_seed``.
tool_registry = ToolRegistry()
