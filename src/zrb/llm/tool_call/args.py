from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


def parse_tool_args(call: "ToolCallPart") -> dict[str, Any] | None:
    """`call.args` as a dict, or `None` if it isn't one.

    `call.args` is either already a dict or a JSON-encoded string (pydantic-ai
    passes either shape depending on the model provider). Returns `None` for
    anything that isn't — or doesn't parse to — a dict, so callers can treat
    "unusable args" as one case regardless of *why* they're unusable.
    """
    args = call.args
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return None
    return args if isinstance(args, dict) else None
