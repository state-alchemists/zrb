"""Tool-call `args`: parsing into a dict, and display helpers.

pydantic-ai gives `args` as a dict, a JSON string, or occasionally something
else.

The one exception to "just parse it" is `purpose`: one line saying what a call
is for, which the narrator speaks and the approval prompt shows. `read_purpose`
is the single reading of it — a spoken line and a shown one must not disagree
about what counts as an answer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
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


PURPOSE_ARGUMENT = "purpose"
"""The argument a tool call may carry to say, in plain words, what it is for."""


def read_purpose(args: object) -> str | None:
    """The ``purpose`` *args* carry, as written; ``None`` when they carry none,
    or an empty one, which leaves the tool's own sentence to say it.

    *args* is a call's arguments, which pydantic-ai holds either as a dict or as
    the JSON string a provider streamed, so a purpose is read the same way by
    whichever line speaks it — the spoken progress line, the spoken approval,
    and the approval prompt.
    """
    purpose = (parse_tool_args_value(args) or {}).get(PURPOSE_ARGUMENT)
    if not isinstance(purpose, str):
        return None
    return purpose.strip() or None


def without_purpose(args: Mapping[str, object]) -> dict[str, object]:
    """*args* with ``purpose`` taken out, for display beside a purpose line.

    The prompt shows the line on its own, so leaving it in the arguments too
    would say the same sentence twice.
    """
    return {key: value for key, value in args.items() if key != PURPOSE_ARGUMENT}


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
