"""A kept tail is measured as the text it is sent as, not as the messages.

The tail is rendered with each tool result clipped to
`TAIL_TOOL_OUTPUT_LIMIT` characters before it goes out, so the unclipped
messages are not what the next request pays for. Budgeting on them kept a tail
that measured 22,614 tokens in hand and sent 5,358 — and printed the first
number, so the banner described a handover that was never built.

The whole-history case is the other half: at split zero nothing is rendered, so
the history costs its own size. Asking the rendered question there answers yes
on a tool-heavy history and keeps it whole, which leaves a compaction that
freed nothing and reports success, every turn.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer import summarize_history
from zrb.llm.summarizer.history_splitter import (
    TAIL_BUDGET_RATIO,
    count_history_tokens,
    count_tail_tokens,
    split_history,
)

HUGE = "y" * 40_000


def _history_with_a_huge_result() -> list:
    """One small turn, then a tool call whose result is 40,000 characters."""
    return [
        ModelRequest(parts=[UserPromptPart(content="run the suite")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="Shell", args={}, tool_call_id="1")]
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Shell", content=HUGE, tool_call_id="1")]
        ),
    ]


def test_the_tail_is_counted_as_the_text_it_is_sent_as():
    """The clip is not free: it happens before the tail is sent, so it has to
    happen before the tail is measured."""
    limiter = LLMLimiter()
    newest = _history_with_a_huge_result()[-1:]

    rendered = count_tail_tokens(limiter, newest)
    as_messages = count_history_tokens(limiter, newest)

    assert as_messages > rendered * 4
    assert rendered > 0


def test_a_huge_tool_result_no_longer_evicts_the_tail():
    """The budget is sized to fit the clipped result, not the raw one.

    This is the defect the measurement caused, in miniature: the raw result is
    over even the retry budget, so the split kept nothing — and a compaction
    that keeps nothing throws away every message of recency it could have had.
    """
    messages = _history_with_a_huge_result()
    limiter = LLMLimiter()
    tail = count_tail_tokens(limiter, messages[-1:])
    threshold = int(tail / TAIL_BUDGET_RATIO) + 1

    # The old currency would have found nothing: the newest message alone is
    # over the loosest budget a retry may use.
    assert count_history_tokens(limiter, messages[-1:]) > threshold * 0.8

    to_summarize, to_keep = split_history(messages, 0, limiter, threshold)

    assert to_keep
    assert to_keep[-1] is messages[-1]
    assert to_summarize == messages[: len(messages) - len(to_keep)]


def test_a_tool_heavy_history_is_still_compacted():
    """Its rendered form fits the tail budget; the history itself does not.

    Keeping it whole would be a compaction that removed nothing: the next turn
    is still over the threshold, asks to compact again, and is told yes.
    """
    messages: list = [
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Shell", content=HUGE, tool_call_id=str(i))]
        )
        for i in range(10)
    ]
    limiter = LLMLimiter()
    threshold = count_history_tokens(limiter, messages)

    # The trap, stated: as a rendered tail this history would fit the budget.
    assert count_tail_tokens(limiter, messages) < threshold * TAIL_BUDGET_RATIO

    to_summarize, to_keep = split_history(messages, 0, limiter, threshold)

    assert to_summarize, "a history over the budget must still be summarized"
    assert to_keep


def _summarizer_agent() -> MagicMock:
    agent = MagicMock()
    result = MagicMock()
    result.output = "<state_snapshot>Summary</state_snapshot>"
    agent.run = AsyncMock(return_value=result)
    return agent


async def _summarize(messages: list, printed: MagicMock, **kwargs) -> list:
    with (
        patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
        ),
        patch(
            "zrb.llm.summarizer.history_summarizer.archive_verbatim_history",
            return_value="written",
        ),
        patch("zrb.llm.summarizer.history_summarizer.zrb_print", printed),
    ):
        return await summarize_history(messages, agent=_summarizer_agent(), **kwargs)


@pytest.mark.asyncio
async def test_the_banner_reports_what_the_tail_weighs():
    """The number the banner prints is the handover's, not the history's."""
    messages = _history_with_a_huge_result()
    limiter = LLMLimiter()
    threshold = int(count_tail_tokens(limiter, messages[-1:]) / TAIL_BUDGET_RATIO) + 1
    printed = MagicMock()

    await _summarize(
        messages, printed, limiter=limiter, conversational_token_threshold=threshold
    )

    banner = next(
        str(call.args[0])
        for call in printed.call_args_list
        if "keeping" in str(call.args[0])
    )
    reported = int(
        banner.split("keeping ")[1].split(" verbatim (")[1].split(" tokens")[0]
    )
    assert 0 < reported < 1_000
    assert reported < count_history_tokens(limiter, messages[-1:])


@pytest.mark.asyncio
async def test_a_split_that_keeps_nothing_although_the_newest_fits_is_reported():
    """Keeping nothing is silent by design when the newest message is simply
    too big. When it fits, the measurement is broken, and that has to be loud:
    the run that kept nothing on every compaction for months printed a zero in
    the banner's ordinary style."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="run the suite")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Shell", content=HUGE, tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="now what?")]),
    ]
    printed = MagicMock()

    with patch(
        "zrb.llm.summarizer.history_splitter.count_tail_tokens",
        return_value=10**9,
    ):
        await _summarize(
            messages,
            printed,
            limiter=LLMLimiter(),
            conversational_token_threshold=100,
        )

    warnings = [str(call.args[0]) for call in printed.call_args_list]
    assert any("no tail was kept" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_a_newest_message_too_big_for_the_budget_is_not_reported():
    """A 40,000-token message over a 100-token threshold is an honest zero: the
    warning must not fire on it, or it would fire on every such history."""
    big = ModelRequest(parts=[UserPromptPart(content="z" * 400_000)])
    messages = [ModelRequest(parts=[UserPromptPart(content="hello")]), big]
    printed = MagicMock()

    await _summarize(
        messages,
        printed,
        limiter=LLMLimiter(),
        conversational_token_threshold=100,
    )

    warnings = [str(call.args[0]) for call in printed.call_args_list]
    assert not any("no tail was kept" in warning for warning in warnings)
