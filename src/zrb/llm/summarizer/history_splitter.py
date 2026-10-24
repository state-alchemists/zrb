import math
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
"""The loosest budget the retry may reach, as a share of the threshold.

A tail budget this tight can fail outright when even the newest message alone
is bigger than it (one huge tool result, say). Before giving up and keeping
nothing, a second attempt is made against a looser budget, which stays under
this ceiling — still under the threshold, just not the headroom-preserving
target — so a compaction still keeps something whenever the history can afford
it at all.
"""

FALLBACK_BUDGET_MULTIPLIER = 2
"""How much looser than the configured budget the retry is.

The retry follows the configured ratio instead of holding a fixed 80%, so
lowering the tail budget cannot be defeated by a retry several times its size:
twice the ratio, capped at `FALLBACK_BUDGET_RATIO`. The default 0.4 therefore
still retries at 0.8, exactly as before.
"""

MIN_TAIL_BUDGET_RATIO = 0.05
"""Smallest tail a setting may ask for.

Below this the tail stops being a conversation — and `0` is not a way to
disable the tail, because it would summarize every message including the
newest, which the tail exists to keep. A caller that wants no verbatim tail
has `LLM_SUMMARY_MAX_TOKEN_RATIO`'s territory; here the floor stands.
"""

MAX_TAIL_BUDGET_RATIO = 0.8
"""Largest tail a setting may ask for.

A tail that fills the threshold leaves no headroom: the history would be back
at the trigger on the very next request, and at exactly 1.0 the split keeps
everything and the summarizer runs on nothing. Capping at the retry ceiling
keeps a compaction worth running — it always frees at least a fifth of the
threshold — and keeps a configured number from silently disabling compaction.
"""


def split_history(
    messages: "list[ModelMessage]",
    summary_window: int,
    limiter: LLMLimiter,
    conversational_token_threshold: int,
    tail_budget_ratio: float = TAIL_BUDGET_RATIO,
    fallback_budget_ratio: float | None = None,
    tail_max_tokens: int | None = None,
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

    `tail_budget_ratio` is clamped into `MIN_TAIL_BUDGET_RATIO` to
    `MAX_TAIL_BUDGET_RATIO`, so a configured `0` still leaves a tail and a
    value past the ceiling still leaves headroom. *tail_max_tokens* is an
    absolute ceiling on the tail as well, whichever of the two is smaller: a
    share of a large window can still be more transcript than the next turn
    wants to re-read.

    Strategy:
    1. Keep the newest turns that fit a tail budget of `tail_budget_ratio` of
       the threshold — token-first, since tokens are what overflow.
    2. If nothing fits that budget (the newest message alone is bigger than
       it), retry against the looser `fallback_budget_ratio`, which defaults to
       twice the budget and never exceeds `FALLBACK_BUDGET_RATIO`.
    3. Never keep more than `summary_window` messages; that count is a
       backstop for histories of many small messages, not the thing that
       decides.
    4. Prefer a turn boundary near the budget edge, when one is available
       without giving up too much of the tail budget to reach it.
    """
    if not messages:
        return [], []
    budget_ratio = _clamp_tail_budget_ratio(tail_budget_ratio)
    if fallback_budget_ratio is None:
        fallback_budget_ratio = _retry_budget_ratio(budget_ratio)
    budget = _capped_budget(
        conversational_token_threshold * budget_ratio, tail_max_tokens
    )
    split_idx = (
        0
        if count_tail_tokens(limiter, messages) <= budget
        else _earliest_split_within_budget(messages, limiter, budget)
    )
    if split_idx == len(messages):
        loose_budget = _capped_budget(
            conversational_token_threshold * fallback_budget_ratio, tail_max_tokens
        )
        if loose_budget > budget:
            split_idx = _earliest_split_within_budget(messages, limiter, loose_budget)
    count_cap = max(0, len(messages) - summary_window) if summary_window > 0 else 0
    split_idx = min(max(split_idx, count_cap), len(messages))
    if split_idx == 0:
        return [], list(messages)
    return messages[:split_idx], messages[split_idx:]


def _capped_budget(budget: float, tail_max_tokens: int | None) -> float:
    """*budget* held under the absolute ceiling, when one is set and positive.

    The ceiling applies to the retry budget too: a cap that a looser retry could
    walk straight past would not be a cap, and the retry exists to keep *some*
    tail, not a bigger one.
    """
    if tail_max_tokens is None or tail_max_tokens <= 0:
        return budget
    return min(budget, float(tail_max_tokens))


def _clamp_tail_budget_ratio(ratio: float) -> float:
    """*ratio* held inside the range a tail budget can mean.

    See `MIN_TAIL_BUDGET_RATIO` and `MAX_TAIL_BUDGET_RATIO` for why the ends
    are where they are. A NaN — an unparsable setting — keeps the shipped
    default rather than producing a NaN budget that compares false against
    every message.
    """
    if math.isnan(ratio):
        return TAIL_BUDGET_RATIO
    return max(MIN_TAIL_BUDGET_RATIO, min(MAX_TAIL_BUDGET_RATIO, ratio))


def _retry_budget_ratio(tail_budget_ratio: float) -> float:
    """The looser budget tried when nothing fits the configured one."""
    return min(FALLBACK_BUDGET_RATIO, tail_budget_ratio * FALLBACK_BUDGET_MULTIPLIER)


def count_tail_tokens(limiter: LLMLimiter, messages: "list[ModelMessage]") -> int:
    """Tokens in a candidate tail, counted as the content it is.

    A tail is measured to decide what to keep, and what is kept is rendered to
    text and sent as one message, so its own size is the quantity that matters.
    The shipped counter would otherwise answer with the usage anchor on the
    newest response: the size of the request that produced it, which covered
    the *whole* history. No tail that includes that response could then ever
    fit a budget below the history's size, and compaction — which only runs
    once the history is at the threshold — would keep nothing every time. On a
    real 414-message history that was 0 kept against 62 messages / 23,977
    tokens counted as content.

    Only the shipped counter is measured this way. A subclass may count
    anything at all, and `_can_binary_search` already declines to assume its
    numbers behave, so its own counter is asked instead.
    """
    if type(limiter) is LLMLimiter:
        return limiter.count_content_tokens(messages)
    return limiter.count_tokens(messages)


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
        tail_tokens = count_tail_tokens(limiter, messages[split_idx:])
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

    Only the shipped counter carries that guarantee. `count_tail_tokens`
    measures flattened text, and dropping the oldest message can only shorten
    what is counted. A subclass may count anything at all, and tiktoken
    re-tokenizes across the dropped boundary, so both keep the linear walk —
    correctness there rests on visiting every index.
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
    if highest < 1 or count_tail_tokens(limiter, messages[highest:]) > budget:
        return None
    lowest = 1
    while lowest < highest:
        middle = (lowest + highest) // 2
        if count_tail_tokens(limiter, messages[middle:]) <= budget:
            highest = middle
        else:
            lowest = middle + 1
    return lowest
