"""Tells the model when a tool call it wrote ran with user-edited args.

`ToolApproved.override_args` changes what executes but not the `ToolCallPart`
in history, so the model would otherwise see a result that doesn't match its
request. Recorded at approval (`agent/run/deferred_calls.py`), consumed at
execution (`agent/common.py::SafeToolsetWrapper.call_tool`). Keyed by the
per-call-unique `tool_call_id`.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.tool_call.args import truncate_tool_args_values

_pending: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}


def record_override(
    tool_call_id: str,
    original_args: dict[str, Any],
    override_args: dict[str, Any],
) -> None:
    """Remember that `tool_call_id` will execute with edited arguments."""
    _pending[tool_call_id] = (original_args, override_args)


def discard_override(tool_call_id: str) -> None:
    """Drop a recorded override for a call that will never execute."""
    _pending.pop(tool_call_id, None)


def pop_override_note(tool_call_id: str | None) -> str | None:
    """Consume the override for `tool_call_id`; the note to append, or `None`."""
    if tool_call_id is None:
        return None
    pending = _pending.pop(tool_call_id, None)
    if pending is None:
        return None
    original_args, override_args = pending
    keys = original_args.keys() | override_args.keys()
    changed = {
        key: override_args.get(key)
        for key in sorted(keys)
        if original_args.get(key) != override_args.get(key)
    }
    if not changed:
        return None
    diff = truncate_tool_args_values(changed, max_length=200)
    return (
        "[SYSTEM NOTE] The user edited this tool call's arguments before it "
        f"ran. Changed argument(s), as actually executed: {diff}. The result "
        "above reflects these edited values, not the arguments you originally "
        "wrote for this call."
    )
