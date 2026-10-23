from typing import TYPE_CHECKING

from zrb.llm.config.limiter import LLMLimiter, is_turn_start

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
one would keep less than this share of the budget, the earliest fitting split
wins instead, so a single huge turn is not summarized whole just to land on a
user message.
"""

FALLBACK_BUDGET_RATIO = 0.8
"""The looser budget tried when nothing fits `TAIL_BUDGET_RATIO`.

A tail budget this tight can fail outright when even the newest message alone
is bigger than it (one huge tool result, say). Before giving up and keeping
nothing, a second attempt is made against 80% of the full threshold — still
under budget, just not the headroom-preserving target — so a compaction still
keeps something whenever the history can afford it at all.
"""


def split_history(
    messages: "list[ModelMessage]",
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
    tail_budget_ratio: float = TAIL_BUDGET_RATIO,
    fallback_budget_ratio: float = FALLBACK_BUDGET_RATIO,
) -> "tuple[list[ModelMessage], list[ModelMessage]]":
    """
    Split history into messages to summarize and messages to keep.

    The kept tail is rendered to plain text by the caller
    (`history_summarizer._render_verbatim_messages`), not resent as structured
    API messages, so — unlike earlier versions of this function — the split
    does not need to avoid landing inside a tool call/return pair: that
    constraint only binds structured messages, and nothing this function
    returns is sent back to the model in structured form once the caller has
    rendered it. The one remaining structural concern, a still-unresolved
    (deferred) tool call, is a narrower one the caller handles separately via
    `zrb.llm.message.pending_tail_start`.

    Strategy:
    1. Keep the newest turns that fit a tail budget of `tail_budget_ratio` of
       the threshold — token-first, since tokens are what overflow.
    2. If nothing fits that budget (the newest message alone is bigger than
       it), retry against the looser `fallback_budget_ratio`.
    3. Never keep more than `summary_window` messages; that count is a
       backstop for histories of many small messages, not the thing that
       decides.
    4. Prefer a turn boundary near the budget edge, when one is available
       without giving up too much of the tail budget to reach it.
    """
    if not messages:
        return [], []
    budget = conversational_token_threshold * tail_budget_ratio
    split_idx = (
        0
        if limiter.count_tokens(messages) <= budget
        else _earliest_split_within_budget(messages, limiter, budget)
    )
    if split_idx == len(messages):
        loose_budget = conversational_token_threshold * fallback_budget_ratio
        if loose_budget > budget:
            split_idx = _earliest_split_within_budget(messages, limiter, loose_budget)
    count_cap = max(0, len(messages) - summary_window) if summary_window > 0 else 0
    split_idx = min(max(split_idx, count_cap), len(messages))
    if split_idx == 0:
        return [], list(messages)
    return messages[:split_idx], messages[split_idx:]


def _earliest_split_within_budget(
    messages: "list[ModelMessage]", limiter: LLMLimiter, budget: float
) -> int:
    """The earliest split whose kept tail fits `budget`, preferring a turn start.

    Walking forward from the start finds the *smallest* index that fits, which
    keeps the most history: the tail lands as close to the budget as the turn
    boundaries allow. Returns ``len(messages)`` (keep nothing) when even the
    newest message alone is over budget.

    Only candidates at or after the first one that fits can be selected, so
    when the counter allows it that first index is bisected instead of walked
    (`_earliest_fitting_split`).
    """
    start = 1
    if _can_binary_search(limiter):
        earliest = _earliest_fitting_split(messages, limiter, budget)
        if earliest is None:
            return len(messages)
        start = earliest
    first_fit = None
    for split_idx in range(start, len(messages)):
        tail_tokens = limiter.count_tokens(messages[split_idx:])
        if tail_tokens > budget:
            continue
        if first_fit is None:
            first_fit = split_idx
        if is_turn_start(messages[split_idx]):
            if tail_tokens >= budget * TURN_START_MIN_SHARE:
                return split_idx
            break
    return first_fit if first_fit is not None else len(messages)


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
