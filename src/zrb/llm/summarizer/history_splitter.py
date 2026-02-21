from typing import Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.llm.message import get_tool_pairs
from zrb.util.cli.style import stylize_yellow


def split_history(
    messages: list[Any],
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
) -> tuple[list[Any], list[Any]]:
    """
    Split history into messages to summarize and messages to keep.

    Strategy:
    1. Try to keep the last `summary_window` messages intact
    2. If that's too many tokens, find a safe split point
    3. If no safe split found, use a best-effort approach that minimizes damage
    """
    # First, try to keep the last summary_window messages
    split_idx = get_split_index(messages, summary_window)
    if split_idx <= 0:
        # Fallback: If no clean turn start found, protect the last 2 messages
        split_idx = max(0, len(messages) - 2)

    to_summarize = messages[:split_idx]
    to_keep = messages[split_idx:]

    # Check if what we're keeping is within token limits
    if to_keep:
        tokens_to_keep = limiter.count_tokens(to_keep)
        if tokens_to_keep > conversational_token_threshold * 0.7:
            # What we want to keep is too large, need to find a better split
            split_idx = find_safe_split_index(
                messages, limiter, conversational_token_threshold
            )
            if split_idx > 0:
                to_summarize = messages[:split_idx]
                to_keep = messages[split_idx:]
            else:
                # No safe split found - use best-effort approach
                to_summarize, to_keep = find_best_effort_split(
                    messages, limiter, conversational_token_threshold
                )

    return to_summarize, to_keep


def get_split_index(messages: list[Any], summary_window: int) -> int:
    """Find the last clean turn start before or at the summary window boundary."""
    if not messages:
        return -1
    # Search from the window boundary backwards, bounded by message count
    start_search_idx = min(len(messages) - 1, max(0, len(messages) - summary_window))
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

        if tokens_to_keep > token_threshold * 0.8:
            # This split keeps too many tokens, skip it
            # But continue searching for splits that keep fewer messages
            continue

        if is_split_safe(messages, split_idx, tool_pairs):
            best_safe_split = split_idx
            if is_turn_start(messages[split_idx]):
                best_boundary_split = split_idx
                # Found a safe split at turn boundary - good enough
                break

    if best_boundary_split != -1:
        return best_boundary_split
    return best_safe_split


def find_best_effort_split(
    messages: list[Any], limiter: "LLMLimiter", token_threshold: int
) -> tuple[list[Any], list[Any]]:
    """
    Find the best possible split when no perfectly safe split exists.

    Strategy:
    1. Try to keep as much recent context as possible while staying under token limit
    2. NEVER break complete tool call/return pairs (Pydantic AI requirement)
    3. Only allow breaking incomplete pairs (calls without returns or returns without calls)
    4. Prefer splits that break fewer incomplete pairs
    """
    from zrb.util.cli.style import stylize_yellow

    tool_pairs = get_tool_pairs(messages)

    best_split_idx = -1
    best_broken_incomplete_pairs = float("inf")
    best_score = -1

    # Try all possible split points from the end
    for split_idx in range(len(messages) - 1, 0, -1):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        # Must stay under token limit (with some buffer)
        if tokens_to_keep > token_threshold * 0.8:
            continue

        # Check if this split would break any complete tool pairs
        # This is ABSOLUTELY NOT ALLOWED per Pydantic AI requirements
        would_break_complete_pair = False
        broken_incomplete_pairs = 0

        for indices in tool_pairs.values():
            call_idx = indices["call_idx"]
            return_idx = indices["return_idx"]

            if call_idx is not None and return_idx is not None:
                # Complete pair - must not be separated
                call_before_split = call_idx < split_idx
                return_before_split = return_idx < split_idx
                if call_before_split != return_before_split:
                    # This would separate a call from its return - NOT ALLOWED
                    would_break_complete_pair = True
                    break
            elif call_idx is not None and return_idx is None:
                # Call without return - if call is before split, we lose it
                if call_idx < split_idx:
                    broken_incomplete_pairs += 1
            elif call_idx is None and return_idx is not None:
                # Return without call (orphaned) - if return is before split, we lose it
                if return_idx < split_idx:
                    broken_incomplete_pairs += 1

        if would_break_complete_pair:
            # Cannot use this split - it violates Pydantic AI requirements
            continue

        # Calculate a score (higher is better)
        # Prefer splits with fewer broken incomplete pairs and more messages kept
        score = (len(to_keep) * 10) - (broken_incomplete_pairs * 50)

        if score > best_score:
            best_score = score
            best_split_idx = split_idx
            best_broken_incomplete_pairs = broken_incomplete_pairs

    if best_split_idx > 0:
        to_summarize = messages[:best_split_idx]
        to_keep = messages[best_split_idx:]
        if best_broken_incomplete_pairs > 0:
            zrb_print(
                stylize_yellow(
                    f"  Warning: Best-effort split loses {best_broken_incomplete_pairs} incomplete tool call/return pair(s)"
                ),
                plain=True,
            )
        return to_summarize, to_keep
    else:
        # Last resort: Summarize everything
        zrb_print(
            stylize_yellow(
                "  Warning: Could not find any split that preserves tool call/return pairs. Summarizing entire history."
            ),
            plain=True,
        )
        return messages, []


def is_split_safe(
    messages: list[Any], split_idx: int, tool_pairs: dict[str, dict[str, int | None]]
) -> bool:
    """
    Check if splitting at the given index would break tool call/return pairs.

    Returns False if splitting would separate a tool call from its return,
    or if it would leave a tool call without its return in the kept messages.
    """
    for tool_call_id, indices in tool_pairs.items():
        call_idx = indices["call_idx"]
        return_idx = indices["return_idx"]

        # If we have both call and return
        if call_idx is not None and return_idx is not None:
            call_before_split = call_idx < split_idx
            return_before_split = return_idx < split_idx

            # They must be on the same side of the split
            if call_before_split != return_before_split:
                # This would separate a call from its return - unsafe
                return False

        # If we have only a call (no return yet)
        elif call_idx is not None and return_idx is None:
            # Tool call without return - if it's before split, we'd lose it
            # If it's after split, it stays in kept messages without return (also problematic)
            # Actually, a call without return in kept messages is OK - the return might come later
            # But if call is before split and we summarize it, we lose the tool call context
            if call_idx < split_idx:
                # Call would be summarized away - we lose the tool call context
                return False
            # Call is in kept messages, return might come in future - this is OK

        # If we have only a return (no call)
        elif call_idx is None and return_idx is not None:
            # Orphaned return - MUST NOT be kept
            if return_idx >= split_idx:
                # If we keep an orphan, the history remains broken
                return False

    return True
