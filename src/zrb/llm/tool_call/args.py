from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart


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
