"""Shared handling for tool-call `args` display: pydantic-ai gives it to us as
either a dict, a JSON-encoded string, or (rarely) something else entirely.
`stream_response.py` (live streaming) and `history_formatter.py` (exported
history text) both need to detect "no meaningful args", parse a JSON-string
dict, and truncate long string values for display — this module is the one
place that logic lives. What each caller does with a non-dict `args` value
(raw passthrough vs. its own truncated-string fallback) is caller-specific
and stays in each caller.
"""

import json
from typing import Any

from zrb.util.truncate import truncate_display

_EMPTY_ARGS_SENTINELS = ("", "null", "{}")


def is_empty_tool_args(args: Any) -> bool:
    """True for args that represent "no meaningful arguments" (None, "", "null", "{}")."""
    if args is None:
        return True
    if isinstance(args, str):
        return args.strip() in _EMPTY_ARGS_SENTINELS
    return False


def parse_tool_args_dict(args: Any) -> dict[str, Any] | None:
    """Best-effort parse of tool-call `args` into a dict.

    Returns `None` if `args` isn't a dict and isn't a JSON string decoding to
    one — the caller decides what to show for that case.
    """
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            obj = json.loads(args)
        except (ValueError, TypeError):
            return None
        if isinstance(obj, dict):
            return obj
    return None


def truncate_tool_args_values(
    kwargs: dict[str, Any], max_length: int = 30, full: bool = False
) -> dict[str, Any]:
    """Truncate string values in a tool-call args dict for display.

    Non-string values pass through untouched. `full` skips truncation
    entirely (used for export transcripts).
    """
    if full:
        return dict(kwargs)
    return {
        key: (truncate_display(val, max_length) if isinstance(val, str) else val)
        for key, val in kwargs.items()
    }
