"""Tool-call `args` display helpers shared by stream_response and history_formatter.

pydantic-ai gives `args` as a dict, a JSON string, or occasionally something
else; parsing into a dict lives in `tool_call/args.py`.
"""

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
