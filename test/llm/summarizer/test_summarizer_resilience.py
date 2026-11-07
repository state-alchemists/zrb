from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.config.config import CFG
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer import (
    create_summarizer_history_processor,
    summarize_history,
    summarize_messages,
)


class MockLimiter(LLMLimiter):
    def count_tokens(self, content) -> int:
        return 10

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text[:max_tokens]


@pytest.mark.asyncio
async def test_summarize_history_resilience():
    "Test that summarize_history handles None for all optional parameters."
    limiter = MockLimiter()
    messages: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    try:
        result = await summarize_history(
            messages,
            agent=None,
            summary_window=None,
            limiter=limiter,
            conversational_token_threshold=None,
        )
        assert result == messages
    except TypeError as e:
        pytest.fail(f"summarize_history crashed with TypeError: {e}")


@pytest.mark.asyncio
async def test_create_summarizer_history_processor_resilience():
    "Test that the processor created handles None parameters gracefully."
    limiter = MockLimiter()
    messages: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    processor = create_summarizer_history_processor(
        conversational_agent=None,
        message_agent=None,
        limiter=limiter,
        conversational_token_threshold=None,
        message_token_threshold=None,
        summary_window=None,
    )

    try:
        result = await processor(messages)
        assert result == messages
    except TypeError as e:
        pytest.fail(f"History processor crashed with TypeError: {e}")


@pytest.mark.asyncio
async def test_summarize_messages_resilience():
    "Test that summarize_messages handles None parameters gracefully."
    limiter = MockLimiter()
    messages: list[ModelMessage] = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="some tool result", tool_name="t", tool_call_id="1"
                )
            ]
        )
    ]

    try:
        result = await summarize_messages(
            messages, agent=None, limiter=limiter, message_token_threshold=None
        )
        assert result == messages
    except TypeError as e:
        pytest.fail(f"summarize_messages crashed with TypeError: {e}")


def test_split_history_resilience():
    "Test that split_history handles potential None values if called directly."
    from zrb.llm.summarizer.history_splitter import split_history

    limiter = MockLimiter()
    messages: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    try:
        to_summarize, to_keep = split_history(
            messages,
            summary_window=0,
            limiter=limiter,
            conversational_token_threshold=0,
        )
        assert isinstance(to_summarize, list)
        assert isinstance(to_keep, list)
    except TypeError as e:
        pytest.fail(f"split_history crashed with TypeError: {e}")


@pytest.mark.asyncio
async def test_processor_survives_unbuildable_summarizer(monkeypatch):
    "A small model whose provider has no credentials must cost the history its"
    import zrb.llm.summarizer.history_summarizer as hs

    def explode():
        raise Exception("Set the `OPENAI_API_KEY` environment variable")

    monkeypatch.setattr(hs, "create_conversational_summarizer_agent", explode)
    messages: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    processor = create_summarizer_history_processor(limiter=MockLimiter())
    result = await processor(messages)

    assert result == messages


class HeavyLimiter(LLMLimiter):
    """Every message costs 10,000 tokens; the whole list, that times its length."""

    def count_tokens(self, content) -> int:
        if isinstance(content, list):
            return len(content) * 10_000
        return 10_000

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text[:max_tokens]


def _ten_user_messages() -> "list[ModelMessage]":
    return [ModelRequest(parts=[UserPromptPart(content=f"q{i}")]) for i in range(10)]


@pytest.mark.asyncio
async def test_auto_conversational_threshold_follows_the_runs_actual_model(
    monkeypatch,
):
    """An unset threshold scales with the run's model, not a flat default.

    100,000 tokens is over gpt-4o's 96,000-token trigger (75% of its known
    128,000 window) but nowhere near deepseek-flash's 750,000-token one (75%
    of its known 1,000,000), so the same history compacts under one model and
    not the other.
    """
    import zrb.llm.summarizer.history_summarizer as hs

    monkeypatch.setattr(hs, "summarize_history", AsyncMock(return_value=["COMPACTED"]))
    # Set well above both models' windows so the per-minute budget never binds
    # here; test_auto_conversational_threshold_is_still_capped_by_the_per_minute_budget
    # covers that bound on its own.
    limiter = HeavyLimiter()
    limiter.max_token_per_minute = 2_000_000
    processor = create_summarizer_history_processor(
        conversational_agent=object(), message_agent=object(), limiter=limiter
    )

    monkeypatch.setattr(hs, "get_current_model", lambda: "openai-chat:gpt-4o")
    assert await processor(_ten_user_messages()) == ["COMPACTED"]

    monkeypatch.setattr(hs, "get_current_model", lambda: "deepseek:deepseek-flash")
    messages = _ten_user_messages()
    assert await processor(list(messages)) == messages


@pytest.mark.asyncio
async def test_auto_conversational_threshold_is_still_capped_by_the_per_minute_budget(
    monkeypatch,
):
    """The rate-limit budget must still cap the auto trigger, same as the old
    model-blind CFG default did -- a model's real context window only replaces
    the model-blind request cap, it doesn't drop the per-minute cap entirely.
    """
    import zrb.llm.summarizer.history_summarizer as hs

    monkeypatch.setattr(hs, "summarize_history", AsyncMock(return_value=["COMPACTED"]))
    limiter = HeavyLimiter()
    limiter.max_token_per_minute = 50_000  # well under deepseek-flash's 1M window
    processor = create_summarizer_history_processor(
        conversational_agent=object(), message_agent=object(), limiter=limiter
    )

    monkeypatch.setattr(hs, "get_current_model", lambda: "deepseek:deepseek-flash")
    # 4 messages (40,000 tokens) already exceeds 75% of the 50,000-token budget
    # (37,500), even though it is nowhere near 75% of the model's real window.
    messages = [ModelRequest(parts=[UserPromptPart(content=f"q{i}")]) for i in range(4)]
    assert await processor(messages) == ["COMPACTED"]


@pytest.mark.asyncio
async def test_an_explicit_conversational_threshold_ignores_the_model(monkeypatch):
    "A threshold passed in stays fixed regardless of which model is running."
    import zrb.llm.summarizer.history_summarizer as hs

    monkeypatch.setattr(hs, "summarize_history", AsyncMock(return_value=["COMPACTED"]))
    processor = create_summarizer_history_processor(
        conversational_agent=object(),
        message_agent=object(),
        limiter=HeavyLimiter(),
        conversational_token_threshold=750_000,
    )

    monkeypatch.setattr(hs, "get_current_model", lambda: "openai-chat:gpt-4o")
    messages = _ten_user_messages()
    assert await processor(list(messages)) == messages


@pytest.mark.asyncio
async def test_auto_message_threshold_follows_the_runs_actual_model(monkeypatch):
    """The tool-result budget is its own knob, not a share of the trigger.

    The old default derived it from the conversational threshold (half of it),
    so a result was only pruned when it approached the whole context window --
    which almost never happened. Pruning is deterministic and cheap, so its
    budget stays small and does not follow the model.
    """
    import zrb.llm.summarizer.history_summarizer as hs

    captured_thresholds = []

    async def fake_summarize_messages(
        messages,
        *,
        agent,
        limiter,
        message_token_threshold,
        conversational_token_threshold,
        **kwargs,
    ):
        captured_thresholds.append(message_token_threshold)
        return messages

    monkeypatch.setattr(hs, "summarize_messages", fake_summarize_messages)
    monkeypatch.setattr(hs, "summarize_history", AsyncMock(return_value=["COMPACTED"]))
    # Set well above both models' windows so the per-minute budget never binds
    # here; the per-minute bound itself is covered on the conversational
    # threshold directly, which the message threshold derives from.
    limiter = HeavyLimiter()
    limiter.max_token_per_minute = 2_000_000
    processor = create_summarizer_history_processor(
        conversational_agent=object(), message_agent=object(), limiter=limiter
    )

    monkeypatch.setattr(hs, "get_current_model", lambda: "openai-chat:gpt-4o")
    await processor(_ten_user_messages())

    monkeypatch.setattr(hs, "get_current_model", lambda: "deepseek:deepseek-flash")
    await processor(_ten_user_messages())

    # Both models prune at the same small budget: the number is the knob, not
    # a share of the model's window.
    expected = CFG.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD
    assert captured_thresholds == [expected, expected]
    assert expected < 20_000


@pytest.mark.asyncio
async def test_an_explicit_message_threshold_ignores_the_model(monkeypatch):
    "A message threshold passed in stays fixed regardless of which model is running."
    import zrb.llm.summarizer.history_summarizer as hs

    captured_thresholds = []

    async def fake_summarize_messages(
        messages,
        *,
        agent,
        limiter,
        message_token_threshold,
        conversational_token_threshold,
        **kwargs,
    ):
        captured_thresholds.append(message_token_threshold)
        return messages

    monkeypatch.setattr(hs, "summarize_messages", fake_summarize_messages)
    monkeypatch.setattr(hs, "summarize_history", AsyncMock(return_value=["COMPACTED"]))
    processor = create_summarizer_history_processor(
        conversational_agent=object(),
        message_agent=object(),
        limiter=HeavyLimiter(),
        message_token_threshold=12_345,
    )

    monkeypatch.setattr(hs, "get_current_model", lambda: "deepseek:deepseek-flash")
    await processor(_ten_user_messages())

    assert captured_thresholds == [12_345]


@pytest.mark.asyncio
async def test_auto_message_threshold_follows_a_pinned_conversational_threshold(
    monkeypatch,
):
    """Pinning the compaction trigger does not move the tool-result budget.

    The two numbers answer different questions: the trigger decides when older
    history is summarized, the budget decides when one result is pruned. They
    were coupled; a pinned trigger used to drag the budget with it.
    """
    import zrb.llm.summarizer.history_summarizer as hs

    captured_thresholds = []

    async def fake_summarize_messages(
        messages,
        *,
        agent,
        limiter,
        message_token_threshold,
        conversational_token_threshold,
        **kwargs,
    ):
        captured_thresholds.append(message_token_threshold)
        return messages

    monkeypatch.setattr(hs, "summarize_messages", fake_summarize_messages)
    monkeypatch.setattr(hs, "summarize_history", AsyncMock(return_value=["COMPACTED"]))
    processor = create_summarizer_history_processor(
        conversational_agent=object(),
        message_agent=object(),
        limiter=HeavyLimiter(),
        conversational_token_threshold=750_000,
    )

    monkeypatch.setattr(hs, "get_current_model", lambda: "openai-chat:gpt-4o")
    await processor(_ten_user_messages())

    assert captured_thresholds == [CFG.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD]


@pytest.mark.asyncio
async def test_tool_results_are_pruned_even_when_the_summarizer_cannot_be_built(
    monkeypatch,
):
    """Pruning is deterministic; only compaction needs a model. A missing
    provider must not leave an oversized tool result in the history."""
    import zrb.llm.summarizer.history_summarizer as hs
    from zrb.llm.summarizer.tool_result_pruner import PRUNED_PREFIX

    def explode():
        raise Exception("Set the `OPENAI_API_KEY` environment variable")

    monkeypatch.setattr(hs, "create_conversational_summarizer_agent", explode)
    messages: list[ModelMessage] = [
        ModelRequest(
            parts=[ToolReturnPart(content="T" * 5_000, tool_name="t", tool_call_id="1")]
        )
    ]

    processor = create_summarizer_history_processor(
        limiter=MockLimiter(), message_token_threshold=5
    )
    result = await processor(messages)

    assert result[0].parts[0].content.startswith(PRUNED_PREFIX)
