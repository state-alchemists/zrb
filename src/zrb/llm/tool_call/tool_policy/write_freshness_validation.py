"""Policy: a whole-file ``Write`` over an existing file needs a current view of it.

Records the Read/Write/Edit transitions that decide freshness (see
``zrb.llm.tool.file_freshness``) and refuses the one call that can silently
destroy work — overwriting a file the model has not seen since it last changed.

Deliberately narrow:

* ``Edit`` is never blocked. ``old_text`` already fails loudly when the model's
  memory has drifted, so a precondition there would be friction without cover.
* Creating a new file is never blocked. There is nothing to be stale about.
* Only ``Write`` onto an **existing** path is gated.

Recording happens after ``next_handler`` so a denied or failed call does not
count as having seen the file.
"""

import json
import os
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart

_READ_TOOLS = ("Read",)
_WRITE_TOOLS = ("Write",)
_EDIT_TOOLS = ("Edit",)


def write_freshness_policy() -> (
    Callable[
        [UIProtocol, "ToolCallPart", Callable[..., Awaitable[Any]]], Awaitable[Any]
    ]
):
    """Build the freshness-tracking tool policy."""

    async def policy(
        ui: UIProtocol,
        call: "ToolCallPart",
        next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
    ) -> Any:
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        from zrb.llm.tool.file_freshness import (
            is_file_fresh,
            is_file_tracked,
            mark_file_fresh,
            mark_file_stale,
        )

        tool = call.tool_name
        if tool not in _READ_TOOLS + _WRITE_TOOLS + _EDIT_TOOLS:
            return await next_handler(ui, call)

        path = _extract_path(call.args)
        if not path:
            return await next_handler(ui, call)

        if tool in _WRITE_TOOLS:
            denial = _stale_write_denial(path, is_file_fresh, is_file_tracked)
            if denial:
                return ToolDenied(denial)

        result = await next_handler(ui, call)
        if _is_refused(result):
            return result
        if tool in _EDIT_TOOLS:
            mark_file_stale(path)
        else:
            mark_file_fresh(path)
        return result

    return policy


def _stale_write_denial(
    path: str,
    is_fresh: Callable[[str], bool],
    is_tracked: Callable[[str], bool],
) -> str | None:
    """Refuse a blind overwrite, naming the one action that unblocks it."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(abs_path):
        return None
    if is_fresh(path):
        return None
    if is_tracked(path):
        return (
            f"Refused: {path} has changed since you last read it in full, so "
            "overwriting it now would discard whatever the change did. "
            "[SYSTEM SUGGESTION]: `Read` it, confirm it says what you think it "
            "says, then write. If you are recovering from a failed edit, the "
            "current content is the thing you are recovering from — read it "
            "first, do not reconstruct it from memory."
        )
    return (
        f"Refused: {path} already exists and you have not read it. "
        "[SYSTEM SUGGESTION]: `Read` it first — a whole-file write replaces "
        "everything that is there, and nothing in this call says what that is. "
        "If you meant to change part of it, use `Edit` instead."
    )


def _is_refused(result: Any) -> bool:
    """Whether the downstream chain denied or errored out of the call."""
    return type(result).__name__ in ("ToolDenied", "ToolError")


def _extract_path(args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return ""
    if not isinstance(args, dict):
        return ""
    path = args.get("path")
    return str(path) if path else ""
