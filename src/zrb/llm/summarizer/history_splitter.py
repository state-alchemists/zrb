from typing import TYPE_CHECKING

from zrb.context.any_context import zrb_print
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.llm.message import get_tool_pairs
from zrb.util.cli.style import stylize_warning

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage

TAIL_BUDGET_RATIO = 0.4
"""Share of the trigger threshold the kept tail may fill.

Compaction runs when the history reaches the trigger threshold. Keeping 40% of
it leaves the rest of the window for the turns that follow, so the summarizer
does not run again on the very next request — the old 70% left so little room
that a compaction could be followed by another almost at once.
"""

TURN_START_MIN_SHARE = 0.5
"""How much of the budget a turn boundary must keep to be preferred.

A turn start is the cleanest place to split, but not at any price: if reaching
one would keep less than this share of the budget, the earliest safe split wins
instead, so a single huge turn is not summarized whole just to land on a user
message.
"""


def split_history(
    messages: "list[ModelMessage]",
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
    tail_budget_ratio: float = TAIL_BUDGET_RATIO,
) -> "tuple[list[ModelMessage], list[ModelMessage]]":
    """
    Split history into messages to summarize and messages to keep.

    Strategy:
    1. Keep the newest turns that fit a tail budget of `tail_budget_ratio` of
       the threshold — token-first, since tokens are what overflow.
    2. Never keep more than `summary_window` messages; that count is a backstop
       for histories of many small messages, not the thing that decides.
    3. Never break a tool call/return pair or split mid-turn where avoidable.
    4. Fall back to the safe-split and best-effort searches when no split fits
       the tail budget at all (one message larger than the budget, say).
    """
    if not messages:
        return [], []
    tool_pairs = get_tool_pairs(messages)
    budget = conversational_token_threshold * tail_budget_ratio
    count_cap = max(0, len(messages) - summary_window) if summary_window > 0 else 0
    budget_split = (
        0
        if limiter.count_tokens(messages) <= budget
        else _split_within_budget(messages, limiter, budget, tool_pairs)
    )
    if budget_split is None:
        return _fallback_split(
            messages, limiter, conversational_token_threshold, tool_pairs
        )
    split_idx = budget_split
    if count_cap > split_idx:
        split_idx = _first_safe_from(messages, count_cap, tool_pairs) or split_idx
    if split_idx == 0:
        return [], list(messages)
    return messages[:split_idx], messages[split_idx:]


def _split_within_budget(
    messages: "list[ModelMessage]",
    limiter: LLMLimiter,
    budget: float,
    tool_pairs: dict,
) -> int | None:
    """The earliest split whose kept tail fits `budget`, preferring a turn start.

    Walking forward from the start finds the *smallest* index that fits, which
    keeps the most history: the tail lands as close to the budget as the turn
    boundaries allow. Returns ``None`` when even the newest message alone is
    over budget.

    Only candidates at or after the first one that fits can be selected, so
    when the counter allows it that first index is bisected instead of walked
    (`_earliest_fitting_split`); every candidate from there still gets the
    tool-pair and turn-start checks below.
    """
    start = 1
    if _can_binary_search(limiter):
        earliest = _earliest_fitting_split(messages, limiter, budget)
        if earliest is None:
            return None
        start = earliest
    first_safe = None
    for split_idx in range(start, len(messages)):
        tail_tokens = limiter.count_tokens(messages[split_idx:])
        if tail_tokens > budget:
            continue
        if not is_split_safe(messages, split_idx, tool_pairs):
            continue
        if first_safe is None:
            first_safe = split_idx
        if is_turn_start(messages[split_idx]):
            if tail_tokens >= budget * TURN_START_MIN_SHARE:
                return split_idx
            break
    return first_safe


def _can_binary_search(limiter: LLMLimiter) -> bool:
    """Whether suffix counts fall monotonically, so the first fit is bisectable.

    Only the shipped counter carries that guarantee. It measures flattened
    text with the char/4 estimate, so dropping the oldest message can only
    shorten what is counted: a usage anchor pins the count for every suffix
    that still holds it, and the trailing `instructions` term can only
    disappear as the suffix shrinks. A subclass may count anything at all,
    and tiktoken re-tokenizes across the dropped boundary, so both keep the
    linear walk — correctness there rests on visiting every index.
    """
    return type(limiter) is LLMLimiter and not limiter.use_tiktoken


def _earliest_fitting_split(
    messages: "list[ModelMessage]", limiter: LLMLimiter, budget: float
) -> int | None:
    """The lowest split whose kept tail fits `budget`, found by bisection.

    Relies on `_can_binary_search(limiter)`: counts never rise as the kept
    tail shrinks, so the first index that fits can be found without visiting
    the indices before it. Returns ``None`` when even the newest message
    alone is over budget.
    """
    highest = len(messages) - 1
    if highest < 1 or limiter.count_tokens(messages[highest:]) > budget:
        return None
    lowest = 1
    while lowest < highest:
        middle = (lowest + highest) // 2
        if limiter.count_tokens(messages[middle:]) <= budget:
            highest = middle
        else:
            lowest = middle + 1
    return lowest


def _first_safe_from(
    messages: "list[ModelMessage]", start: int, tool_pairs: dict
) -> int | None:
    """The first split at or after *start* that keeps tool pairs intact.

    A turn start is preferred; a merely safe split is the fallback.
    """
    first_safe = None
    for split_idx in range(start, len(messages)):
        if not is_split_safe(messages, split_idx, tool_pairs):
            continue
        if first_safe is None:
            first_safe = split_idx
        if is_turn_start(messages[split_idx]):
            return split_idx
    return first_safe


def _fallback_split(
    messages: "list[ModelMessage]",
    limiter: LLMLimiter,
    conversational_token_threshold: int,
    tool_pairs: dict,
) -> "tuple[list[ModelMessage], list[ModelMessage]]":
    """Split without a usable tail budget: safe splits first, then best effort."""
    split_idx = find_safe_split_index(
        messages, limiter, conversational_token_threshold, tool_pairs
    )
    if split_idx >= 0:
        return messages[:split_idx], messages[split_idx:]
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


def find_safe_split_index(
    messages: "list[ModelMessage]",
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

    Returns `(would_break_complete_pair, broken_incomplete_pairs)`. When the
    first is True the split must be rejected and the count is meaningless.
    """
    would_break_complete_pair = False
    broken_incomplete_pairs = 0

    for indices in tool_pairs.values():
        call_idx = indices["call_idx"]
        return_idx = indices["return_idx"]

        if call_idx is not None and return_idx is not None:
            if (call_idx < split_idx) != (return_idx < split_idx):
                would_break_complete_pair = True
                break
        elif call_idx is not None:
            if call_idx < split_idx:
                broken_incomplete_pairs += 1
        elif return_idx is not None:
            if return_idx >= split_idx:
                would_break_complete_pair = True
                break
            broken_incomplete_pairs += 1

    return would_break_complete_pair, broken_incomplete_pairs


def find_best_effort_split(
    messages: "list[ModelMessage]",
    limiter: "LLMLimiter",
    token_threshold: int,
    tool_pairs: dict | None = None,
) -> "tuple[list[ModelMessage], list[ModelMessage]]":
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

        if tokens_to_keep > token_threshold * 0.8:
            continue

        would_break_complete_pair, broken_incomplete_pairs = _classify_split(
            tool_pairs, split_idx
        )
        if would_break_complete_pair:
            continue

        # Higher is better: more messages kept, fewer incomplete pairs lost.
        score = (len(to_keep) * 10) - (broken_incomplete_pairs * 50)

        if score > best_score:
            best_score = score
            best_split_idx = split_idx
            best_broken_incomplete_pairs = broken_incomplete_pairs

    if best_split_idx < 0:
        zrb_print(
            stylize_warning(
                "  Warning: Could not find any split that preserves tool call/return pairs. Summarizing entire history."
            ),
            plain=True,
        )
        return messages, []
    if best_broken_incomplete_pairs > 0:
        zrb_print(
            stylize_warning(
                f"  Warning: Best-effort split loses {best_broken_incomplete_pairs} incomplete tool call/return pair(s)"
            ),
            plain=True,
        )
    return messages[:best_split_idx], messages[best_split_idx:]


def is_split_safe(
    messages: "list[ModelMessage]",
    split_idx: int,
    tool_pairs: dict[str, dict[str, int | None]],
) -> bool:
    """Check if splitting at the given index would break tool call/return pairs.

    Unsafe: separating a complete pair, summarizing away a pending call, or
    keeping an orphaned return. A pending call on the kept side is safe.
    """
    for indices in tool_pairs.values():
        call_idx = indices["call_idx"]
        return_idx = indices["return_idx"]
        if call_idx is not None and return_idx is not None:
            if (call_idx < split_idx) != (return_idx < split_idx):
                return False
        elif call_idx is not None:
            if call_idx < split_idx:
                return False
        elif return_idx is not None and return_idx >= split_idx:
            return False
    return True
