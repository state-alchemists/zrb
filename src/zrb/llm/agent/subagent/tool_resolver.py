"""Resolve tool names (Claude-compatible aliases honored) into tool objects.

Kept dependency-free (no ``zrb.llm.tool``/``zrb.llm.common_tools`` imports) so
it can be called from both `SubAgentManager` and hook code without pulling in
the whole tool package (and, transitively, `pydantic_ai`) just to resolve a
name.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

# Claude Code names its shell tool ``Bash``; zrb ships a single ``Shell`` tool.
# A sub-agent file (or hook config) written for Claude that lists ``Bash``
# maps onto ``Shell``, so a `tools:`/`disallowedTools:` list keeps working
# unmodified (case-insensitive, e.g. ``Bash`` or ``bash``).
_TOOL_NAME_ALIASES = {"bash": "Shell"}


def canonical_tool_name(name: str) -> str:
    """The zrb tool name that implements the Claude-compatible name *name*."""
    return _TOOL_NAME_ALIASES.get(name.lower(), name)


def resolved_tool_name(tool: Any) -> str | None:
    """The registered name of *tool* — its `Tool.name`, or a plain function's
    `__name__`."""
    raw = getattr(tool, "name", None)
    if raw is not None:
        return raw
    return getattr(tool, "__name__", None)


def resolve_tools_by_name(
    names: Sequence[str],
    registry: "dict[str, Any]",
    factories: Sequence[Callable[[Any], Any]] = (),
    ctx: Any = None,
) -> list[Any]:
    """Resolve *names* against *registry* first, then against tools produced
    by *factories* (evaluated against *ctx*) for any name the registry
    doesn't cover.

    The registry alone is what `SubAgentManager` has always used for a sub-
    agent's named `tools:` list — it only holds statically-registered tools
    (`common_tools.py`'s `_seed_default_tools`). Config-gated tools such as the
    journal ones are registered as factories instead and are invisible to a
    registry-only lookup; passing *factories* lets a caller (a hook, for
    example) name those too. Delegate tools are always excluded. A name that
    matches nothing resolves to nothing, silently — the same behavior the
    registry-only lookup already had.
    """
    resolved: list[Any] = []
    remaining: list[str] = []
    for name in names:
        canon = canonical_tool_name(name)
        tool = registry.get(canon)
        if tool is not None:
            if not getattr(tool, "zrb_is_delegate_tool", False):
                resolved.append(tool)
        else:
            remaining.append(canon)

    if not remaining or not factories:
        return resolved

    wanted = set(remaining)
    for factory in factories:
        produced = factory(ctx)
        produced_list = produced if isinstance(produced, list) else [produced]
        for tool in produced_list:
            if resolved_tool_name(tool) in wanted and not getattr(
                tool, "zrb_is_delegate_tool", False
            ):
                resolved.append(tool)
    return resolved
