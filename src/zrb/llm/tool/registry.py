"""The canonical tool registry.

``tool_registry`` owns the ordered set of static tools, per-run tool
factories, and toolset factories that zrb agents are built with. It is the
*default*: ``apply_common_tools`` feeds a host from this registry, and a task
or manager overrides it at construction or by an explicit ``set_tools``.

Tools are an **ordered pipeline** — registry order *is* the agent's tool-list
order — so the mutation verbs are ``append_tool`` / ``prepend_tool``, with
``set_tools`` for wholesale replacement and ``remove_tool`` to drop by value
or registered name. Every mutation is a concrete edit of the resolved list:
appending to a registry that still carries its lazy default freezes that
default first, so appends become part of the resolved set.

The default itself is a *lazy seed*: a zero-argument callable returning the
built-in tool/factory/toolset lists. It is stored, never called here — the
built-ins transitively import ``pydantic_ai``, so ``_seed``'s heavy imports
run only when the registry is first resolved (i.e. on the first agent build,
replacing the deferral ``common_tools.py`` used to do with
``defer_common_tools`` on each host).
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
    """Registered name of *tool*, whether it is a bare function or a ``Tool``.

    A ``Tool`` wraps the function it was built from, and zrb's tools carry
    their PascalCase name on ``__name__``, so both layers have to
    be tried.
    """
    fn = getattr(tool, "function", tool)
    return getattr(fn, "__name__", "") or getattr(tool, "name", "") or ""


class ToolRegistry:
    """The ordered canonical set of tools + factories for zrb agents.

    A bare ``ToolRegistry()`` is empty until mutated; the default registry
    (``tool_registry``) carries a lazy *seed* of the built-in tools. Any
    mutation materializes the current resolved set first, so appends layer on
    the built-ins and ``set_tools`` replaces them wholesale.
    """

    def __init__(self, default: Callable[[], ToolSeed] | None = None) -> None:
        """Create an empty registry.

        default: an optional lazy seed callable returning the
        ``(tools, tool_factories, toolset_factories)`` triple, resolved (and
        materialized) on the first read instead of at construction.
        """
        self._seed = default
        self._tools: list[ToolLike] = []
        self._tool_factories: list[ToolFactory] = []
        self._toolset_factories: list[ToolsetFactory] = []
        self._materialized = False

    # ---- resolution ----------------------------------------------------

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
        """The ``LLM_TOOLS`` name allowlist, or ``[]`` meaning "all".

        The env twin of this registry: when non-empty, only
        the named static tools survive resolution. Read lazily so env changes
        and later ``CFG`` edits are honored at resolve time.
        """
        return list(CFG.LLM_TOOLS or [])

    def get_tools(self) -> list[ToolLike]:
        """The resolved static tools, in order.

        When ``CFG.LLM_TOOLS`` names a non-empty allowlist, only those tools
        are returned (factory/toolset tools are not name-known statically and
        are unaffected)."""
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

    # ---- ordered mutations ------------------------------------------------

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
        """Drop a static tool by value or by registered name.

        Every matching entry (identity first, then ``tool_name``) is removed,
        so ``remove_tool("EnterWorktree")`` and
        ``remove_tool(enter_worktree)`` behave alike.
        """
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

    # ---- application ----------------------------------------------------

    def set_seed(self, seed: Callable[[], ToolSeed]) -> None:
        """Install *seed* as the lazy default, unless already materialized.

        Used by ``zrb.llm.common_tools`` to hand the registry the built-in
        tool content without triggering its ``pydantic_ai`` imports (the seed
        is stored, not called, until first resolution). A registry that
        already resolved (or was explicitly set) keeps its content.
        """
        if not self._materialized:
            self._seed = seed

    def apply_to(self, host) -> None:
        """Register every tool, factory, and toolset factory on *host*.

        *host* conforms to the ``CommonToolHost`` protocol
        (``append_tool``/``append_tool_factory``/``append_toolset_factory``).
        Called once per host; calling twice registers everything twice.
        """
        host.append_tool(*self.get_tools())
        host.append_tool_factory(*self.get_tool_factories())
        host.append_toolset_factory(*self.get_toolset_factories())


#: The shared tool registry every zrb agent starts from. Its built-in seed is
#: wired (lazily) in ``zrb.llm.common_tools``.
tool_registry = ToolRegistry()
