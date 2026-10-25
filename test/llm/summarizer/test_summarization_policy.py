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
from zrb.llm.summarizer import history_summarizer
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


class TextLimiter(LLMLimiter):
    """A message costs one token per character of its parts, so sizes are exact."""

    def count_tokens(self, content) -> int:
        if isinstance(content, list):
            return sum(self.count_tokens(message) for message in content)
        parts = getattr(content, "parts", None)
        if parts is None:
            return len(str(content))
        return sum(len(str(getattr(part, "content", ""))) for part in parts)

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


def test_the_tail_budget_is_configurable_and_defaults_to_the_constant(monkeypatch):
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_HISTORY_TAIL_BUDGET_RATIO", raising=False)

    assert CFG.DEFAULT_LLM_HISTORY_TAIL_BUDGET_RATIO == str(TAIL_BUDGET_RATIO)
    assert CFG.LLM_HISTORY_TAIL_BUDGET_RATIO == TAIL_BUDGET_RATIO


def test_a_smaller_budget_also_shrinks_the_retry():
    """The retry follows the setting instead of a fixed 80%, so lowering the
    tail budget cannot be undone by a retry several times its size.

    Threshold 100 and ratio 0.2 give a budget of 20, while the newest message
    alone is 25: the split therefore falls to the retry. Twice the ratio is 40
    and keeps that one message; the old fixed 80% would have kept the 55-token
    message before it as well.
    """
    limiter = TextLimiter()
    messages: list = [_user("a" * 30), _user("b" * 55), _user("c" * 25)]

    _, to_keep = split_history(
        messages,
        summary_window=300,
        limiter=limiter,
        conversational_token_threshold=100,
        tail_budget_ratio=0.2,
    )

    assert to_keep == [messages[-1]]


def test_a_zero_budget_still_keeps_a_tail():
    """`0` would summarize every message including the newest, so it is clamped
    up to the floor rather than obeyed."""
    limiter = FixedLimiter(per_message=10)
    messages = _turns(5)  # 10 messages, 100 tokens

    to_summarize, to_keep = split_history(
        messages, 300, limiter, 100, tail_budget_ratio=0.0
    )

    assert to_keep
    assert to_summarize


def test_a_budget_past_the_ceiling_still_leaves_headroom():
    """A tail that filled the threshold would disable compaction, so the
    setting is clamped to the retry ceiling, not obeyed."""
    limiter = FixedLimiter(per_message=10)
    messages = _turns(5)  # 100 tokens

    to_summarize, to_keep = split_history(
        messages, 300, limiter, 100, tail_budget_ratio=5.0
    )

    assert len(to_keep) == 8  # 0.8 of 100 tokens
    assert len(to_summarize) == 2


def test_an_unparsable_budget_falls_back_to_the_default():
    limiter = FixedLimiter(per_message=10)
    messages = _turns(5)

    default = split_history(messages, 300, limiter, 100)
    unparsable = split_history(
        messages, 300, limiter, 100, tail_budget_ratio=float("nan")
    )

    assert unparsable == default


@pytest.mark.asyncio
async def test_the_configured_tail_budget_reaches_the_split(tmp_path, monkeypatch):
    """The setting is read on every call, so `/set` takes effect without a
    restart, and the number that reaches the splitter is the configured one."""
    from unittest.mock import AsyncMock, MagicMock

    captured = {}

    def capture_split(
        messages,
        summary_window,
        limiter,
        threshold,
        tail_budget_ratio=TAIL_BUDGET_RATIO,
        tail_max_tokens=None,
    ):
        captured["tail_budget_ratio"] = tail_budget_ratio
        captured["tail_max_tokens"] = tail_max_tokens
        return messages, []

    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(CFG, "LLM_HISTORY_TAIL_BUDGET_RATIO", 0.25, raising=False)
    monkeypatch.setattr(history_summarizer, "split_history", capture_split)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))
    processor = history_summarizer.create_summarizer_history_processor(
        conversational_agent=agent,
        message_agent=agent,
        limiter=FixedLimiter(per_message=10),
        conversational_token_threshold=100,
        summary_window=300,
    )

    await processor(_turns(6))  # 12 messages, 120 tokens: over the threshold

    assert captured["tail_budget_ratio"] == 0.25


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


@pytest.mark.asyncio
async def test_the_split_is_printed_so_a_tail_is_never_a_guess(tmp_path, monkeypatch):
    """The old banner printed the limits and the result, and neither said
    whether a tail had been kept: `chunk 1/1 (366 messages)` only means "no
    tail" if you already know that count is the summarized half. The split is
    printed when it is decided, on both sides of it."""
    from unittest.mock import AsyncMock, MagicMock, patch

    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=MagicMock(output="<state_snapshot>s</state_snapshot>")
    )

    with patch("zrb.llm.summarizer.history_summarizer.zrb_print") as printed:
        await history_summarizer.summarize_history(
            _turns(6),  # 12 messages, 10 tokens each; a 100-token trigger
            agent=agent,
            summary_window=300,
            limiter=FixedLimiter(per_message=10),
            conversational_token_threshold=100,
        )

    banner = " ".join(str(call) for call in printed.call_args_list)
    assert "Summarizing 8 messages (80 tokens)" in banner
    assert "keeping 4 verbatim (40 tokens)" in banner


@pytest.mark.asyncio
async def test_the_summary_is_written_from_the_whole_conversation(
    tmp_path, monkeypatch
):
    """What is kept is not what is read.

    `<where_we_are>`, `<now>` and `<next>` are the next agent's headline, and a
    summarizer that never saw the kept tail writes them for the moment the split
    fell on — a whole work episode before the newest messages it then reads
    verbatim, so it asks for work those messages already finished.
    """
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=MagicMock(output="<state_snapshot>s</state_snapshot>")
    )

    await history_summarizer.summarize_history(
        _turns(6),  # 12 messages; the last 4 are kept verbatim
        agent=agent,
        summary_window=300,
        limiter=FixedLimiter(per_message=10),
        conversational_token_threshold=100,
    )

    prompts = [
        call.args[0]
        for call in agent.run.call_args_list
        if call.args and isinstance(call.args[0], str)
    ]
    assert prompts, "the summarizer was never called"
    assert any(
        "question 5" in prompt for prompt in prompts
    ), "the kept tail never reached the summarizer"
