"""Tells the model when a tool call it wrote actually ran with different args.

`ToolApproved.override_args` (pydantic-ai) swaps the arguments used for
validation and execution when a human edits a tool call during approval, but
it never rewrites the `ToolCallPart` already sitting in the model's own turn
in message history. Left alone, the model's next turn sees its own original
request next to a `ToolReturnPart` that doesn't match it, with no signal that
a human intervened.

`record_override` is called once approval resolves to an edited
`ToolApproved` (`agent/run/deferred_calls.py::process_deferred_requests`).
`pop_override_note` is called once, at execution time
(`agent/common.py::SafeToolsetWrapper.call_tool`), to consume it and build the
text appended to that call's tool result via `_append_tool_context`. Keyed by
`tool_call_id`, which pydantic-ai guarantees unique per call, so no per-run
scoping is needed — an entry that's never claimed (an edited call that ends up
never executing) is a handful of small dicts, not a real leak.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.util.tool_args import truncate_tool_args_values

_pending: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}


def record_override(
    tool_call_id: str,
    original_args: dict[str, Any],
    override_args: dict[str, Any],
) -> None:
    """Remember that `tool_call_id` will execute with edited arguments."""
    _pending[tool_call_id] = (original_args, override_args)


def discard_override(tool_call_id: str) -> None:
    """Drop a recorded override for `tool_call_id` without consuming it.

    Called when a call that recorded an override turns out to never execute
    (e.g. `rebuild_for_denials` clears its whole batch because a sibling call
    in the same batch was denied) — otherwise that entry would sit in
    `_pending` forever, since only execution-time `pop_override_note` removes
    entries. A no-op if nothing was recorded for this id.
    """
    _pending.pop(tool_call_id, None)


def pop_override_note(tool_call_id: str | None) -> str | None:
    """Consume the override recorded for `tool_call_id`, if any.

    Returns the system note to append to that call's tool result, or `None`
    when this call's arguments were never edited (the overwhelmingly common
    case — this is a dict lookup, not a loop) or `tool_call_id` itself is
    unknown (some toolset call contexts don't carry one).
    """
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
