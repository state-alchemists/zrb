"""What the compaction trigger saw at a round boundary, measured and not acted on.

A round is one `agent.run()`. The history processors run before a turn's first
round and never inside the rounds that follow, so a turn whose tool work keeps
the model calling can cross the token trigger and stay past it: on 2026-11-24 one
turn made 36 calls above the threshold in forty-eight minutes. Whether a check
inside such a round would pay for itself is a question about how many calls are
left after the crossing, and nothing in the logs answered it.

This module answers it, and only that. It measures the boundary and the usage
line carries the numbers; nothing here changes what is sent, and no threshold in
it is a policy — a rule built on these rows has to prove itself on them before it
may spend a model call.

`history_tokens` is `count_tokens(history)`, the call the trigger itself makes,
so it carries the provider's usage anchor where the history holds one. It is not
the record's `input_tokens`, which adds the system prompt and the typed message
to it, and not `count_content_tokens`, which ignores the anchor.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from zrb.llm.contracts.shared.usage_log import RoundBudget

if TYPE_CHECKING:
    from zrb.llm.contracts.config.limiter import LLMLimiter

MASK_AGE_MESSAGES = 20
"""How far back a probe looks for tool results it would consider masking.

Twenty messages is about three tool rounds of a chat, and the results older than
that are most of a long history's mass. A probe's window, not a policy: this
module measures what masking them would free and what re-sending the rest would
cost, and leaves both in the log.
"""


def measure_round_budget(
    history: Sequence[object],
    limiter: "LLMLimiter",
    *,
    requests_before: int,
    trigger_tokens: int,
    system_tokens: int,
    message_window: int,
    is_result_pending: bool = False,
    gap_seconds: float | None = None,
) -> RoundBudget:
    """Measure *history* as the trigger would, and what a mask would cost.

    *requests_before* is how many model calls this turn had already made, which
    is the count a mid-turn rule would be gated on: it says how much of the turn
    is behind the boundary rather than how large the send is.
    *is_result_pending* is the deferred-call guard — a round that is about to
    resume approved calls must not have its history rewritten, and the row says
    so rather than leaving the next reader to infer it.
    *gap_seconds* is the wait since the previous round ended: the provider's
    cache has a lifetime of minutes, and a rewrite right after one is free.
    """
    tool_tokens, mask_resend_tokens = _measure_maskable(history, limiter)
    history_tokens = limiter.count_tokens(history)
    return RoundBudget(
        requests_before=requests_before,
        history_tokens=history_tokens,
        messages=len(history),
        tool_tokens=tool_tokens,
        mask_resend_tokens=mask_resend_tokens,
        trigger_tokens=trigger_tokens,
        system_tokens=system_tokens,
        message_window=message_window,
        is_over_trigger=(
            history_tokens > _allowed_tokens(trigger_tokens, system_tokens)
            or len(history) > message_window
        ),
        is_result_pending=is_result_pending,
        gap_seconds=gap_seconds,
    )


def _allowed_tokens(trigger_tokens: int, system_tokens: int) -> int:
    """The history allowance the trigger measures against, floored at one.

    The trigger counts the system prompt against its own threshold
    (`_maybe_compress_history`), and a prompt larger than the threshold leaves a
    one-token allowance rather than a negative one. Same floor here, so the
    probe's answer matches the decision it is describing.
    """
    return max(1, trigger_tokens - system_tokens)


def _measure_maskable(
    history: Sequence[object], limiter: "LLMLimiter"
) -> tuple[int, int]:
    """Tokens in the tool results older than `MASK_AGE_MESSAGES`, and the re-send.

    The second number is what a mask would cost: everything from the oldest
    masked message on has to be sent again at full price, because a provider's
    prompt cache is a prefix. A mask near the start of a history therefore costs
    almost the whole send, and one near the end costs little.
    """
    cutoff = max(0, len(history) - MASK_AGE_MESSAGES)
    oldest = -1
    tool_tokens = 0
    for index in range(cutoff):
        tokens = _tool_return_tokens(history[index], limiter)
        if tokens > 0 and oldest < 0:
            oldest = index
        tool_tokens += tokens
    if oldest < 0:
        return 0, 0
    return tool_tokens, limiter.count_content_tokens(history[oldest:])


def _tool_return_tokens(message: object, limiter: "LLMLimiter") -> int:
    """Tokens carried by one message's tool results; zero for anything else."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.agent.types import ToolReturnPart

    return sum(
        limiter.count_content_tokens(part)
        for part in getattr(message, "parts", ()) or ()
        if isinstance(part, ToolReturnPart)
    )
