"""Tests for LLM history summarizer logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)

from zrb.llm.summarizer.history_splitter import find_best_effort_split
from zrb.llm.summarizer.history_summarizer import summarize_history, summarize_messages
from zrb.llm.summarizer.text_summarizer import summarize_text, summarize_text_plain


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(self.count_tokens(m) for m in content)
        return 10

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_summarize_messages_resilience():
    # Verify that summarizer handles invalid message objects gracefully
    messages = ["invalid message object"]
    result = await summarize_messages(messages)
    assert result == messages


@pytest.mark.asyncio
async def test_summarize_history_handles_none():
    limiter = MockLimiter()
    result = await summarize_history(None, limiter=limiter)
    assert result is None


@pytest.mark.asyncio
async def test_summarize_text_extracts_snapshot():
    # Verify behavioral snapshot extraction
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Intro <state_snapshot>Important State</state_snapshot> Outro"
    agent.run = AsyncMock(return_value=mock_result)

    result = await summarize_text("history", agent)
    assert result == "<state_snapshot>Important State</state_snapshot>"


@pytest.mark.asyncio
async def test_summarize_text_plain_edge_cases():
    limiter = MockLimiter()
    agent = MagicMock()
    # Threshold too low
    res = await summarize_text_plain("some text", agent, limiter, 0)
    assert "[Threshold too low" in res
    # Non-string input
    res = await summarize_text_plain(123, agent, limiter, 100)
    assert res == "123"


@pytest.mark.asyncio
async def test_find_best_effort_split_empty():
    limiter = MockLimiter()
    to_sum, to_keep = find_best_effort_split([], limiter, 100)
    assert to_sum == []
    assert to_keep == []
