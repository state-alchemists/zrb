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
from zrb.llm.summarizer.text_summarizer import (
    summarize_long_text,
    summarize_short_text,
    summarize_text,
    summarize_text_plain,
)


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


class TestSummarizeShortText:
    """Test summarize_short_text through public API."""

    @pytest.mark.asyncio
    async def test_summarize_short_text_success(self):
        """Test successful summarization of short text."""
        limiter = MockLimiter()
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Summary of the text"
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_short_text("Short text", agent, limiter, 100)
        assert result == "Summary of the text"

    @pytest.mark.asyncio
    async def test_summarize_short_text_truncates_long_result(self):
        """Test that long summaries are truncated to threshold."""
        limiter = MockLimiter()
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "A" * 200  # Much longer than threshold
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_short_text("Short text", agent, limiter, 50)
        # Limiter truncates to 50 chars
        assert len(result) == 50

    @pytest.mark.asyncio
    async def test_summarize_short_text_non_string_output(self):
        """Test handling non-string output."""
        limiter = MockLimiter()
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = 123  # Non-string output
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_short_text("Short text", agent, limiter, 100)
        assert result == "123"

    @pytest.mark.asyncio
    async def test_summarize_short_text_none_output(self):
        """Test handling None output."""
        limiter = MockLimiter()
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = None
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_short_text("Short text", agent, limiter, 100)
        assert result == ""

    @pytest.mark.asyncio
    async def test_summarize_short_text_raises_on_error(self):
        """Test that errors are raised after logging."""
        limiter = MockLimiter()
        agent = MagicMock()
        agent.run = AsyncMock(side_effect=RuntimeError("Agent error"))

        with pytest.raises(RuntimeError, match="Agent error"):
            await summarize_short_text("Short text", agent, limiter, 100)


class TestSummarizeLongText:
    """Test summarize_long_text through public API."""

    @pytest.mark.asyncio
    async def test_summarize_long_text_single_chunk(self):
        """Test summarization when text fits in one chunk."""
        limiter = MockLimiter()
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Chunk summary"
        agent.run = AsyncMock(return_value=mock_result)

        # Text that needs chunking
        result = await summarize_long_text("A" * 150, agent, limiter, 100)
        assert result == "Chunk summary"

    @pytest.mark.asyncio
    async def test_summarize_long_text_depth_limit(self):
        """Test summarization stops at depth limit."""
        limiter = MockLimiter()
        agent = MagicMock()

        # Depth > 5 returns truncated text
        result = await summarize_long_text("Long text", agent, limiter, 100, depth=6)
        assert result == "Long text"[:100]


class TestSummarizeText:
    """Test summarize_text through public API."""

    @pytest.mark.asyncio
    async def test_summarize_text_partial_flag(self):
        """Test summarize_text with partial flag."""
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Partial summary"
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_text("history", agent, partial=True)
        assert result == "Partial summary"
        # Verify the prompt includes "partial conversation"
        call_args = agent.run.call_args[0][0]
        assert "partial conversation" in call_args.lower()

    @pytest.mark.asyncio
    async def test_summarize_text_non_string_output(self):
        """Test summarize_text with non-string output."""
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = 12345
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_text("history", agent)
        assert result == "12345"

    @pytest.mark.asyncio
    async def test_summarize_text_none_output(self):
        """Test summarize_text with None output."""
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = None
        agent.run = AsyncMock(return_value=mock_result)

        result = await summarize_text("history", agent)
        assert result == ""

    @pytest.mark.asyncio
    async def test_summarize_text_raises_on_error(self):
        """Test summarize_text raises errors."""
        agent = MagicMock()
        agent.run = AsyncMock(side_effect=RuntimeError("Error"))

        with pytest.raises(RuntimeError):
            await summarize_text("history", agent)


class TestSummarizeTextPlain:
    """Additional tests for summarize_text_plain."""

    @pytest.mark.asyncio
    async def test_summarize_text_plain_short_text(self):
        """Test that short text is summarized directly."""
        limiter = MockLimiter()
        agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Summary"
        agent.run = AsyncMock(return_value=mock_result)

        # Short text (under threshold)
        result = await summarize_text_plain("Short", agent, limiter, 100)
        assert result == "Summary"

    @pytest.mark.asyncio
    async def test_summarize_text_plain_non_convertible(self):
        """Test handling non-convertible input."""
        limiter = MockLimiter()
        agent = MagicMock()

        # Object that can't be converted to string normally
        class BadObject:
            def __str__(self):
                raise TypeError("Cannot convert")

        # Should return "[Unconvertible content]"
        result = await summarize_text_plain(BadObject(), agent, limiter, 100)
        assert result == "[Unconvertible content]"
