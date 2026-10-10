"""Tool-call `args`: parsing into a dict, and display helpers.

pydantic-ai gives `args` as a dict, a JSON string, or occasionally something
else.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from zrb.util.truncate import truncate_display

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart

_EMPTY_ARGS_SENTINELS = ("", "null", "{}")


def parse_tool_args_value(args: Any) -> dict[str, Any] | None:
    """A tool-call `args` value (dict or JSON string) as a dict, else `None`."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return None
    return args if isinstance(args, dict) else None


def parse_tool_args(call: "ToolCallPart") -> dict[str, Any] | None:
    """`call.args` as a dict, or `None` if it isn't one. See `parse_tool_args_value`."""
    return parse_tool_args_value(call.args)


def is_empty_tool_args(args: Any) -> bool:
    """True for args that represent "no meaningful arguments" (None, "", "null", "{}")."""
    if args is None:
        return True
    if isinstance(args, str):
        return args.strip() in _EMPTY_ARGS_SENTINELS
    return False


def truncate_tool_args_values(
    kwargs: dict[str, Any], max_length: int = 30, full: bool = False
) -> dict[str, Any]:
    """Truncate string values for display; `full` skips truncation."""
    if full:
        return dict(kwargs)
    return {
        key: (truncate_display(val, max_length) if isinstance(val, str) else val)
        for key, val in kwargs.items()
    }
