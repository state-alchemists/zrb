"""Policy: notice when the same attempt is being made over and over.

``workflow.md`` already says to change what you are testing by the third try,
or stop and report. Prose did not hold it. One benchmarked trial spent 89 tool
calls across **four files** — 32 shell runs and 45 writes — re-running the same
simulation against the same code until the 600s budget ran out, having written
mid-run that "the changes did not yield the intended results" and then
continuing anyway.

So the count is kept here instead. This never denies: an agent legitimately
re-runs a test suite many times, and refusing that would be worse than the loop
it prevents. It appends a ``[SYSTEM SUGGESTION]`` to the result, once per
threshold crossing, so the observation arrives *while* the loop is running
rather than in a rule read hundreds of calls earlier.
"""

import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.llm.tool_call.handler import UIProtocol
from zrb.llm.tool_call.tool_policy.repetition_state import (
    bump_repetition,
    mark_repetition_warned,
    was_repetition_warned,
)

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart

_TRACKED_TOOLS = ("Shell", "Bash")


def repetition_policy() -> (
    Callable[
        [UIProtocol, "ToolCallPart", Callable[..., Awaitable[Any]]], Awaitable[Any]
    ]
):
    """Build the repeated-attempt tool policy."""

    async def policy(
        ui: UIProtocol,
        call: "ToolCallPart",
        next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
    ) -> Any:
        threshold = CFG.LLM_REPEATED_ATTEMPT_THRESHOLD
        if threshold <= 0 or call.tool_name not in _TRACKED_TOOLS:
            return await next_handler(ui, call)

        signature = _signature(call)
        if not signature:
            return await next_handler(ui, call)

        count = bump_repetition(signature)
        result = await next_handler(ui, call)
        if count < threshold or was_repetition_warned(signature):
            return result
        mark_repetition_warned(signature)
        return _append_note(result, _note(count))

    return policy


def _note(count: int) -> str:
    return (
        f"\n\n[SYSTEM SUGGESTION]: This is attempt {count} at the same command. "
        "An attempt that repeats input you have already run is not new evidence, "
        "and the result above is one you have already seen. Change what you are "
        "testing — read the code path rather than re-running it, add output that "
        "would distinguish your competing hypotheses, or narrow the case to the "
        "smallest failing one. If you cannot name what this attempt would tell "
        "you that the last one did not, stop and report what you cannot get past."
    )


def _append_note(result: Any, note: str) -> Any:
    """Attach the nudge to a string result; leave any other shape untouched."""
    if isinstance(result, str):
        return result + note
    return result


def _signature(call: "ToolCallPart") -> str:
    """Identify "the same attempt" by the command text alone.

    Deliberately exact rather than fuzzy: a model that varies its command *is*
    changing what it tests, which is the behaviour being asked for. Only a
    byte-identical re-run is treated as a repeat.
    """
    args = call.args
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return ""
    if not isinstance(args, dict):
        return ""
    command = args.get("command")
    if not command:
        return ""
    return f"{call.tool_name}:{str(command).strip()}"
