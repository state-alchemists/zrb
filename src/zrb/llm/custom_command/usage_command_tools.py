"""The `/usage` Tools section: which tools were called, and which never were."""

from __future__ import annotations

from collections.abc import Iterable

from zrb.llm.tool_registry import tool_name, tool_registry
from zrb.llm.usage_log import UsageRecord

_TOP_TOOLS = 8
_NEVER_CALLED_SHOWN = 12


def get_registered_tool_names() -> list[str]:
    """The names of the tools registered on this machine right now.

    Tools a factory produces per run (MCP, LSP, worktree) are not here, so the
    never-called list is relative to this fixed set."""
    return sorted({name for name in map(tool_name, tool_registry.get_tools()) if name})


def render_tools_section(
    records: list[UsageRecord], registered: list[str]
) -> list[str]:
    """The lines of the Tools section; empty when no run counted a tool."""
    calls = _sum_counts(record.tool_counts for record in records)
    if not calls:
        return []
    errors = _sum_counts(record.tool_errors for record in records)
    ranked = sorted(calls.items(), key=lambda item: (-item[1], item[0]))
    lines = ["  Tools"]
    for name, count in ranked[:_TOP_TOOLS]:
        failed = errors.get(name, 0)
        detail = f"{failed} error(s)" if failed else ""
        lines.append(f"    {name:<28}{count:>6} call(s)  {detail}".rstrip())
    if len(ranked) > _TOP_TOOLS:
        lines.append(f"    +{len(ranked) - _TOP_TOOLS} more tool(s) called")
    lines.extend(_never_called(calls, registered))
    return lines


def _never_called(calls: dict[str, int], registered: list[str]) -> list[str]:
    idle = sorted(name for name in registered if name not in calls)
    if not idle:
        return []
    shown = ", ".join(idle[:_NEVER_CALLED_SHOWN])
    more = len(idle) - _NEVER_CALLED_SHOWN
    suffix = f", +{more} more" if more > 0 else ""
    return [
        f"    never called ({len(idle)} of {len(registered)} registered on this "
        f"machine): {shown}{suffix}"
    ]


def _sum_counts(maps: Iterable[dict[str, int]]) -> dict[str, int]:
    total: dict[str, int] = {}
    for counts in maps:
        for name, count in counts.items():
            total[name] = total.get(name, 0) + count
    return total
