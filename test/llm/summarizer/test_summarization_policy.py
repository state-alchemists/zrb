"""The compaction policy: trigger at 75% of the budget, keep a 40% tail.

These tests pin the numbers the summarizer runs on. They are deliberately
about behavior (what is kept, when compaction triggers) rather than about the
private helpers that implement it.
"""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.config.config import CFG
from zrb.config.helper import get_max_token_threshold
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.history_splitter import TAIL_BUDGET_RATIO, split_history


class FixedLimiter(LLMLimiter):
    """Every message costs the same, so a split index is easy to predict."""

    def __init__(self, per_message: int = 10):
        super().__init__()
        self.per_message = per_message

    def count_tokens(self, content) -> int:
        if isinstance(content, list):
            return len(content) * self.per_message
        return self.per_message

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text


def _user(content: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=content)])


def _turns(count: int):
    messages = []
    for index in range(count):
        messages.append(_user(f"question {index}"))
        messages.append(ModelResponse(parts=[]))
    return messages


def test_the_tail_budget_is_forty_percent_of_the_trigger():
    assert TAIL_BUDGET_RATIO == 0.4


def test_the_tail_is_the_newest_turns_that_fit_the_budget():
    limiter = FixedLimiter(per_message=10)
    messages = _turns(5)  # 10 messages, 100 tokens
    # Trigger 100 -> tail budget 40 tokens -> 4 messages.
    to_summarize, to_keep = split_history(
        messages,
        summary_window=300,
        limiter=limiter,
        conversational_token_threshold=100,
    )

    assert len(to_keep) == 4
    assert len(to_summarize) == 6
    # The tail is the newest messages, the summarized part the oldest.
    assert to_keep[-1] is messages[-1]
    assert to_summarize[0] is messages[0]


def test_the_split_lands_on_a_turn_start_when_one_fits_the_budget():
    limiter = FixedLimiter(per_message=10)
    messages = _turns(5)
    # Only the user prompts start a turn; the assistant replies do not.
    with_turn_starts = [
        i for i, m in enumerate(messages) if isinstance(m, ModelRequest)
    ]

    _, to_keep = split_history(
        messages,
        summary_window=300,
        limiter=limiter,
        conversational_token_threshold=100,
    )

    split = len(messages) - len(to_keep)
    assert split in with_turn_starts


def test_a_giant_single_turn_is_not_summarized_whole():
    """Reaching a user message cannot cost the whole budget: a long tool loop
    (one turn, many messages) still keeps the newest messages verbatim."""
    limiter = FixedLimiter(per_message=10)
    messages = [_user("start")]
    messages += [ModelResponse(parts=[]) for _ in range(6)]
    messages += [ModelResponse(parts=[]) for _ in range(2)]
    messages += [_user("late question")]  # a turn start only at the very end
    # Trigger 100 -> budget 40: the budget boundary is index 6 (4 messages),
    # but the only turn start in reach keeps 10 tokens, under half the budget.
    _, to_keep = split_history(
        messages,
        summary_window=300,
        limiter=limiter,
        conversational_token_threshold=100,
    )

    assert len(to_keep) == 4
    assert to_keep[-1] is messages[-1]


def test_the_message_window_is_a_backstop_for_short_messages():
    limiter = FixedLimiter(per_message=1)
    messages = _turns(10)  # 20 messages, 20 tokens: well under the budget
    # The window still bounds what is kept when the count is what overflows.
    to_summarize, to_keep = split_history(
        messages, summary_window=6, limiter=limiter, conversational_token_threshold=100
    )

    assert len(to_keep) == 6
    assert len(to_summarize) == 14


def test_a_split_no_longer_needs_to_avoid_a_tool_pair():
    """The kept tail is rendered to text by the caller, not resent as
    structured messages, so a split landing inside a tool call/return pair is
    no longer special-cased: it is purely a token-budget cut."""
    limiter = FixedLimiter(per_message=10)
    call = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args={}, tool_call_id="1")]
    )
    result = ModelRequest(
        parts=[ToolReturnPart(tool_name="read_file", content="x", tool_call_id="1")]
    )
    messages = [
        _user("please read it"),
        ModelResponse(parts=[]),
        ModelResponse(parts=[]),
        call,
        result,
        ModelResponse(parts=[]),
    ]
    # Trigger 50 -> budget 20 (2 messages): the boundary lands inside the pair
    # (the call at index 3, its result at index 4), which the old splitter
    # refused and snapped forward past instead.
    to_summarize, to_keep = split_history(
        messages, summary_window=300, limiter=limiter, conversational_token_threshold=50
    )

    assert to_keep == messages[4:]
    assert to_summarize == messages[:4]
    assert call in to_summarize and result in to_keep


def test_a_tool_pair_spanning_almost_the_whole_history_still_keeps_a_tail():
    """Regression guard: a call paired with a return near the very end used to
    force the whole history into one chunk (`to_keep` came back empty, no
    split was both within budget and pairing-safe). The budget-only split
    keeps whatever the tail budget affords regardless of the pair."""
    limiter = FixedLimiter(per_message=10)
    call = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args={}, tool_call_id="1")]
    )
    filler = [ModelResponse(parts=[]) for _ in range(20)]
    result = ModelRequest(
        parts=[ToolReturnPart(tool_name="read_file", content="x", tool_call_id="1")]
    )
    messages = [_user("please read it"), call, *filler, result]

    to_summarize, to_keep = split_history(
        messages,
        summary_window=300,
        limiter=limiter,
        conversational_token_threshold=100,
    )

    assert to_keep
    assert to_summarize
    assert call in to_summarize


def test_the_default_window_is_300_messages():
    assert CFG.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW == "300"


def test_the_trigger_defaults_to_three_quarters_of_the_prompt_budget(monkeypatch):
    monkeypatch.delenv(
        f"{CFG.ENV_PREFIX}_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD",
        raising=False,
    )
    cap = min(CFG.LLM_MAX_TOKEN_PER_MINUTE, CFG.LLM_MAX_TOKEN_PER_REQUEST)

    assert CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == (
        get_max_token_threshold(0.75, cap, cap)
    )


def test_a_configured_trigger_is_clamped_to_three_quarters(monkeypatch):
    cap = min(CFG.LLM_MAX_TOKEN_PER_MINUTE, CFG.LLM_MAX_TOKEN_PER_REQUEST)
    monkeypatch.setattr(
        CFG,
        "LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD",
        str(cap * 10),
        raising=False,
    )

    assert CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == (
        get_max_token_threshold(0.75, cap, cap)
    )
