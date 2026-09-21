from typing import Any

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.llm.message import get_tool_pairs
from zrb.util.cli.style import stylize_warning


def split_history(
    messages: list[Any],
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
) -> tuple[list[Any], list[Any]]:
    """
    Split history into messages to summarize and messages to keep.

    Strategy:
    1. Retain latest `summary_window` messages (or fewer if token limit forces).
    2. Find a SAFE split point near the target that respects tool pairs and turn boundaries.
    3. If no safe split at target, adjust while staying close to the retention policy.
    4. Fallback to best-effort if no safe split exists.
    """
    if not messages:
        return [], []

    tool_pairs = get_tool_pairs(messages)
    # Try to keep summary_window messages, but at least 1 and at most all messages
    target_idx = len(messages) - min(summary_window, len(messages))
    budget = conversational_token_threshold * 0.7

    for search in (_search_back_from_target, _search_forward_from_target):
        split_idx = search(messages, target_idx, limiter, budget, tool_pairs)
        if split_idx is not None:
            return messages[:split_idx], messages[split_idx:]

    # 3. Fallback to finding the largest safe split under 80% token threshold
    split_idx = find_safe_split_index(
        messages, limiter, conversational_token_threshold, tool_pairs
    )
    if split_idx >= 0:
        return messages[:split_idx], messages[split_idx:]

    # 4. No safe split found - use best-effort approach
    to_summarize, to_keep = find_best_effort_split(
        messages, limiter, conversational_token_threshold, tool_pairs
    )
    if to_summarize or to_keep:
        return to_summarize, to_keep

    # Absolute last resort: keep as few messages as possible while still
    # respecting tool pairs. Walk backwards until we find a safe split.
    for split_idx in range(len(messages) - 1, 0, -1):
        if is_split_safe(messages, split_idx, tool_pairs):
            return messages[:split_idx], messages[split_idx:]
    # Cannot split without breaking a pair — summarize everything.
    return messages, []


def _search_back_from_target(
    messages: list[Any],
    target_idx: int,
    limiter: LLMLimiter,
    budget: float,
    tool_pairs: dict,
) -> int | None:
    """Walk back from the target for a turn start, keeping MORE messages.

    Stops as soon as the retained side outgrows `budget`, since walking
    further back only makes it larger.
    """
    for split_idx in range(min(target_idx, len(messages) - 1), 0, -1):
        if limiter.count_tokens(messages[split_idx:]) > budget:
            return None
        if is_split_safe(messages, split_idx, tool_pairs) and is_turn_start(
            messages[split_idx]
        ):
            return split_idx
    return None


def _search_forward_from_target(
    messages: list[Any],
    target_idx: int,
    limiter: LLMLimiter,
    budget: float,
    tool_pairs: dict,
) -> int | None:
    """Walk forward from the target, keeping FEWER messages.

    Prefers the first turn start that fits the budget, and falls back to the
    earliest merely-safe split when no turn start does.
    """
    best_safe_idx = None
    for split_idx in range(target_idx, len(messages)):
        if limiter.count_tokens(messages[split_idx:]) > budget:
            continue
        if not is_split_safe(messages, split_idx, tool_pairs):
            continue
        if best_safe_idx is None:
            best_safe_idx = split_idx
        if is_turn_start(messages[split_idx]):
            return split_idx
    return best_safe_idx


def find_safe_split_index(
    messages: list[Any],
    limiter: "LLMLimiter",
    token_threshold: int,
    tool_pairs: dict | None = None,
) -> int:
    """
    Find a safe split index that doesn't break tool call/return pairs.
    Returns -1 if no safe split is possible.

    Strategy:
    1. Try to keep as many recent messages as possible while staying under token limit.
    2. Ensure tool call/return pairs are not separated.
    3. Prefer splits at conversation turn boundaries.
    """
    if not messages:
        return -1
    if tool_pairs is None:
        tool_pairs = get_tool_pairs(messages)

    best_safe_split = -1

    for split_idx in range(1, len(messages)):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        if tokens_to_keep > token_threshold * 0.8:
            continue

        if is_split_safe(messages, split_idx, tool_pairs):
            if best_safe_split == -1:
                best_safe_split = split_idx

            if is_turn_start(messages[split_idx]):
                return split_idx

    return best_safe_split


def _classify_split(
    tool_pairs: dict[str, dict[str, int | None]], split_idx: int
) -> tuple[bool, int]:
    """Classify a candidate split against every tool call/return pair.

    Returns `(would_break_complete_pair, broken_incomplete_pairs)`:
    - `would_break_complete_pair`: separating a complete call/return pair
      across the split, or keeping an already-orphaned return — both
      forbidden by Pydantic AI. A caller must reject the split outright when
      this is True; the incomplete-pair count is meaningless in that case.
    - `broken_incomplete_pairs`: how many incomplete pairs (a call with no
      return yet, or an orphaned return being summarized away) this split
      loses. Used only to score otherwise-valid splits against each other.
    """
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
                would_break_complete_pair = True
                break
        elif call_idx is not None and return_idx is None:
            if call_idx < split_idx:
                broken_incomplete_pairs += 1
        elif call_idx is None and return_idx is not None:
            if return_idx >= split_idx:
                would_break_complete_pair = True
                break
            broken_incomplete_pairs += 1

    return would_break_complete_pair, broken_incomplete_pairs


def find_best_effort_split(
    messages: list[Any],
    limiter: "LLMLimiter",
    token_threshold: int,
    tool_pairs: dict | None = None,
) -> tuple[list[Any], list[Any]]:
    """
    Find the best possible split when no perfectly safe split exists.

    Strategy:
    1. Try to keep as much recent context as possible while staying under token limit
    2. NEVER break complete tool call/return pairs (Pydantic AI requirement)
    3. Only allow breaking incomplete pairs (calls without returns or returns without calls)
    4. Prefer splits that break fewer incomplete pairs
    """
    if not messages:
        return [], []
    if tool_pairs is None:
        tool_pairs = get_tool_pairs(messages)

    best_split_idx = -1
    best_broken_incomplete_pairs = float("inf")
    best_score = -1

    for split_idx in range(len(messages), 0, -1):
        to_keep = messages[split_idx:]
        tokens_to_keep = limiter.count_tokens(to_keep)

        # Must stay under token limit (with some buffer)
        if tokens_to_keep > token_threshold * 0.8:
            continue

        would_break_complete_pair, broken_incomplete_pairs = _classify_split(
            tool_pairs, split_idx
        )
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

    if best_split_idx >= 0:
        to_summarize = messages[:best_split_idx]
        to_keep = messages[best_split_idx:]
        if best_broken_incomplete_pairs > 0:
            zrb_print(
                stylize_warning(
                    f"  Warning: Best-effort split loses {best_broken_incomplete_pairs} incomplete tool call/return pair(s)"
                ),
                plain=True,
            )
        return to_summarize, to_keep
    else:
        # Last resort: Summarize everything
        zrb_print(
            stylize_warning(
                "  Warning: Could not find any split that preserves tool call/return pairs. Summarizing entire history."
            ),
            plain=True,
        )
        return messages, []


def is_split_safe(
    messages: list[Any], split_idx: int, tool_pairs: dict[str, dict[str, int | None]]
) -> bool:
    """Check if splitting at the given index would break tool call/return pairs.

    A split is unsafe when it would:
    1. Separate a complete call/return pair across the split (either side).
    2. Summarize away a call whose return is kept — the kept return would end
       up orphaned, with no call to explain it.
    3. Keep an already-orphaned return that has no call anywhere.

    A call with no return yet that lands in the *kept* messages is safe: the
    return may simply arrive in a later turn, so there's nothing lost by
    keeping it as-is.
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
            # Losing the call to summarization would discard its context with
            # nothing left to explain a future return - unsafe. Keeping it
            # (return_idx is None either side of the split) is fine.
            if call_idx < split_idx:
                return False

        # If we have only a return (no call)
        elif call_idx is None and return_idx is not None:
            # Orphaned return - MUST NOT be kept
            if return_idx >= split_idx:
                # If we keep an orphan, the history remains broken
                return False

    return True
