from typing import Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.util.cli.style import stylize_error, stylize_yellow


def split_history(
    messages: list[Any],
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
) -> tuple[list[Any], list[Any]]:
    # We always protect the last 2 messages (the active turn) as a bare minimum
    # to prevent the agent from losing its immediate context/data.
    split_idx = get_split_index(messages, summary_window)
    if split_idx <= 0:
        # Fallback: If no clean turn start found, protect the last 2 messages
        split_idx = max(0, len(messages) - 2)
    to_summarize = messages[:split_idx]
    to_keep = messages[split_idx:]
    # Handle 'to_summarize'
    if not to_summarize:
        # If nothing to summarize (short history) but token count is high,
        # we need to find a safe split point that doesn't break tool call/return pairs.
        split_idx = find_safe_split_index(
            messages, limiter, conversational_token_threshold
        )
        if split_idx > 0:
            to_summarize = messages[:split_idx]
            to_keep = messages[split_idx:]
        else:
            # No safe split found - we have to summarize everything
            # This is risky but necessary when token count is too high
            zrb_print(
                stylize_yellow(
                    "  Warning: No safe split point found, summarizing entire history..."
                ),
                plain=True,
            )
            to_summarize = messages
            to_keep = []
    return to_summarize, to_keep


def get_split_index(messages: list[Any], summary_window: int) -> int:
    """Find the last clean turn start before the summary window."""
    start_search_idx = max(0, len(messages) - summary_window - 1)
    for i in range(start_search_idx, -1, -1):
        if is_turn_start(messages[i]):
            return i
    return -1


def find_safe_split_index(
    messages: list[Any], limiter: "LLMLimiter", token_threshold: int
) -> int:
    """
    Find a safe split index that doesn't break tool call/return pairs.
    Returns -1 if no safe split is possible.

    Strategy:
    1. Try to keep as many recent messages as possible while staying under token limit
    2. Ensure tool call/return pairs are not separated
    3. Prefer splits at conversation turn boundaries
    """
    tool_pairs = get_tool_pairs(messages)

    best_boundary_split = -1
    best_safe_split = -1

    for split_idx in range(len(messages) - 1, 0, -1):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        if tokens_to_keep > token_threshold * 0.7:
            # We reached the point where it's too big.
            # We can't keep more context. Stop searching lower indices.
            break

        if is_split_safe(messages, split_idx, tool_pairs):
            best_safe_split = split_idx
            if is_turn_start(messages[split_idx]):
                best_boundary_split = split_idx

    if best_boundary_split != -1:
        return best_boundary_split
    return best_safe_split


def get_tool_pairs(messages: list[Any]) -> dict[str, dict[str, int | None]]:
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    tool_pairs = {}
    for i, msg in enumerate(messages):
        msg_parts = getattr(msg, "parts", [])
        for part in msg_parts:
            if isinstance(part, ToolCallPart):
                tool_call_id = getattr(part, "tool_call_id", None)
                if tool_call_id is not None:
                    tool_pairs[tool_call_id] = {"call_idx": i, "return_idx": None}
            elif isinstance(part, ToolReturnPart):
                tool_call_id = getattr(part, "tool_call_id", None)
                if tool_call_id is not None:
                    if tool_call_id in tool_pairs:
                        tool_pairs[tool_call_id]["return_idx"] = i
                    else:
                        # Orphaned return or return preceding call (unlikely but handle)
                        tool_pairs[tool_call_id] = {"call_idx": None, "return_idx": i}
    return tool_pairs


def is_split_safe(
    messages: list[Any], split_idx: int, tool_pairs: dict[str, dict[str, int | None]]
) -> bool:
    """
    Check if splitting at the given index would break tool call/return pairs.
    """
    for indices in tool_pairs.values():
        call_idx = indices["call_idx"]
        return_idx = indices["return_idx"]

        # If we have both call and return
        if call_idx is not None and return_idx is not None:
            call_before_split = call_idx < split_idx
            return_before_split = return_idx < split_idx

            # They must be on the same side of the split
            if call_before_split != return_before_split:
                return False

        # If we have only a call (no return yet)
        elif call_idx is not None and return_idx is None:
            # Tool call without return - if it's before split, we'd lose it
            if call_idx < split_idx:
                return False

        # If we have only a return (no call)
        elif call_idx is None and return_idx is not None:
            return False

    return True
