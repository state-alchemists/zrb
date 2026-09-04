from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from pydantic_ai.messages import (
        AudioUrl,
        BinaryContent,
        DocumentUrl,
        ImageUrl,
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
        VideoUrl,
    )
except ImportError:

    @dataclass
    class ModelRequest:
        parts: list[Any] = field(default_factory=list)

    @dataclass
    class ModelResponse:
        parts: list[Any] = field(default_factory=list)

    @dataclass
    class TextPart:
        content: str

    @dataclass
    class UserPromptPart:
        content: Any

    @dataclass
    class SystemPromptPart:
        content: str

    @dataclass
    class ToolReturnPart:
        content: str
        tool_name: str = "test"
        tool_call_id: str = "123"

    @dataclass
    class ToolCallPart:
        tool_name: str
        args: dict[str, Any]
        tool_call_id: str

    @dataclass
    class BinaryContent:
        data: bytes
        media_type: str

    @dataclass
    class ImageUrl:
        url: str

    @dataclass
    class AudioUrl:
        url: str

    @dataclass
    class VideoUrl:
        url: str

    @dataclass
    class DocumentUrl:
        url: str


from zrb.llm.summarizer import (
    find_safe_split_index,
    message_to_text,
    process_message_for_summarization,
    process_tool_return_part,
    summarize_history,
    summarize_long_text,
    summarize_text_plain,
)
from zrb.llm.summarizer.text_summarizer import summarize_short_text


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(self.count_tokens(m) for m in content)
        if hasattr(content, "parts"):
            return sum(
                self.count_tokens(p.content)
                for p in content.parts
                if hasattr(p, "content")
            )
        # For logic tests that expect 1000 for non-strings
        return 1000

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_summarize_history_preserves_first_user_message():
    """The opening user turn survives compaction verbatim (force=True)."""
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "summary text"
    agent.run = AsyncMock(return_value=mock_result)

    opening_request = "refactor the parser and fix the failing test"
    messages = [
        ModelRequest(parts=[UserPromptPart(content=opening_request)]),
        ModelRequest(parts=[UserPromptPart(content="b" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="c" * 50)]),
    ]

    with (
        patch("zrb.llm.config.limiter.is_turn_start", return_value=True),
        patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            return_value="old conversation summary",
        ),
        patch(
            "zrb.llm.summarizer.history_summarizer.render_journal_index",
            return_value=None,
        ),
    ):
        new_history = await summarize_history(
            messages, agent=agent, limiter=limiter, force=True
        )

    combined = "\n".join(message_to_text(m) for m in new_history)
    assert opening_request in combined  # verbatim first user turn survived
    assert "old conversation summary" in combined  # summary still present


@pytest.mark.asyncio
async def test_summarize_history_second_round_preserves_the_true_first_user_message():
    """A second compaction round must not mistake the first round's own
    synthetic summary message for the real first user message — it's a
    ModelRequest/UserPromptPart too, and sits at index 0 after round 1."""
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "summary text"
    agent.run = AsyncMock(return_value=mock_result)

    opening_request = "refactor the parser and fix the failing test"
    round1_messages = [
        ModelRequest(parts=[UserPromptPart(content=opening_request)]),
        ModelRequest(parts=[UserPromptPart(content="b" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="c" * 50)]),
    ]

    with (
        patch("zrb.llm.config.limiter.is_turn_start", return_value=True),
        patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            return_value="round 1 summary",
        ),
        patch(
            "zrb.llm.summarizer.history_summarizer.render_journal_index",
            return_value=None,
        ),
    ):
        round1_result = await summarize_history(
            round1_messages, agent=agent, limiter=limiter, force=True
        )

    round2_messages = round1_result + [
        ModelRequest(parts=[UserPromptPart(content="d" * 50)]),
    ]

    with (
        patch("zrb.llm.config.limiter.is_turn_start", return_value=True),
        patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            return_value="round 2 summary",
        ),
        patch(
            "zrb.llm.summarizer.history_summarizer.render_journal_index",
            return_value=None,
        ),
    ):
        round2_result = await summarize_history(
            round2_messages, agent=agent, limiter=limiter, force=True
        )

    combined = "\n".join(message_to_text(m) for m in round2_result)
    assert opening_request in combined
    # Round 1's own synthetic summary text must not be duplicated forward —
    # only the real user content it was fused with survives into round 2.
    assert "round 1 summary" not in combined


@pytest.mark.asyncio
async def test_find_safe_split_index_no_safe_split():
    limiter = MockLimiter()
    messages = [
        ModelRequest(parts=[ToolCallPart(tool_name="t", args={}, tool_call_id="1")]),
        ModelRequest(parts=[UserPromptPart(content="Waiting...")]),
    ]
    idx = find_safe_split_index(messages, limiter, 5)
    assert idx == -1


@pytest.mark.asyncio
async def test_process_message_for_summarization_non_request():
    msg = ModelResponse(parts=[TextPart(content="hi")])
    res = await process_message_for_summarization(msg, None, None, 10, 20)
    assert res == msg


@pytest.mark.asyncio
async def test_process_tool_return_part_edge_cases():
    limiter = MockLimiter()
    # 1. Non-string content
    part = ToolReturnPart(content={"a": 1}, tool_name="t")
    res, mod = await process_tool_return_part(part, None, limiter, 10, 20)
    assert mod is False

    # 2. Already summarized
    part = ToolReturnPart(content="SUMMARY OF TOOL RESULT: ...", tool_name="t")
    res, mod = await process_tool_return_part(part, None, limiter, 10, 20)
    assert mod is False

    # 3. Low threshold (Warning path)
    part = ToolReturnPart(content="Very long content...", tool_name="t")
    res, mod = await process_tool_return_part(part, None, limiter, 5, 20)
    assert mod is True
    assert "TRUNCATED" in res.content


@pytest.mark.asyncio
async def test_summarize_text_plain_edge_cases():
    limiter = MockLimiter()
    # 1. Non-string text
    assert await summarize_text_plain(123, None, limiter, 10) == "123"

    # 2. Low threshold
    assert (
        await summarize_text_plain("hi", None, limiter, 0)
        == "[Threshold too low for summarization]"
    )


@pytest.mark.asyncio
async def test_summarize_heavy_recent_history():
    # Setup
    limiter = MockLimiter()
    agent = MagicMock()

    # Mock agent.run returning a result with output
    mock_result = MagicMock()
    mock_result.output = "SUMMARY"
    agent.run = AsyncMock(return_value=mock_result)

    # Create 2 messages
    msg1 = ModelRequest(parts=[UserPromptPart(content="Hello")])
    msg2 = ModelResponse(parts=[TextPart(content="A" * 100)])
    messages = [msg1, msg2]

    # Run with small threshold (10) and normal window (5)
    # Since limiter returns 1000 for list, it is > 10.
    # Since len(messages) is 2, it is <= 5.
    # The safe split logic should trigger.

    new_history = await summarize_history(
        messages,
        agent=agent,
        summary_window=5,
        limiter=limiter,
        conversational_token_threshold=10,
    )

    # Assert
    # With the new safer logic that NEVER breaks complete tool pairs:
    # - No tool pairs exist in these messages
    # - But threshold is too low (10) for any message (mocked as 1000 tokens)
    # So find_best_effort_split returns full summarization (messages, [])
    # We get 1 message: summary
    assert len(new_history) == 1
    assert isinstance(new_history[0], ModelRequest)  # Summary

    # Verify agent was called
    assert agent.run.called


@pytest.mark.asyncio
async def test_summarize_history_error_handling():
    """Test that summarize_history returns original messages if agent fails."""
    limiter = MockLimiter()
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=Exception("Summarizer failed"))

    messages = [
        ModelRequest(parts=[UserPromptPart(content="a" * 100)]),
        ModelRequest(parts=[UserPromptPart(content="b" * 100)]),
    ]

    with patch("zrb.llm.config.limiter.is_turn_start", return_value=True):
        new_history = await summarize_history(
            messages,
            agent=agent,
            summary_window=0,
            limiter=limiter,
            conversational_token_threshold=10,
        )

    # Should return original messages on error
    assert new_history == messages


def test_message_to_text_unknown_types():
    """Test message_to_text with unknown message and part types."""
    # Unknown message type
    assert message_to_text(123) == "123"

    # Unknown part type in ModelRequest
    class UnknownPart:
        pass

    req = ModelRequest(parts=[UnknownPart()])
    assert "Unknown part type: UnknownPart" in message_to_text(req)

    # ModelResponse with unknown parts
    res = ModelResponse(parts=[UnknownPart()])
    assert "Unknown response part: UnknownPart" in message_to_text(res)


@pytest.mark.asyncio
async def test_summarize_short_text_non_string_output():
    """Test summarize_short_text when agent returns non-string output."""
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = 12345  # Non-string output
    agent.run = AsyncMock(return_value=mock_result)

    summary = await summarize_short_text("some text", agent, limiter, 100)
    assert summary == "12345"


@pytest.mark.asyncio
async def test_summarize_long_text_consolidation_failure():
    """Test summarize_long_text when consolidation fails."""
    limiter = MockLimiter()
    agent = MagicMock()

    # First calls (chunk summaries) succeed, consolidation fails
    mock_chunk_result = MagicMock()
    mock_chunk_result.output = "Chunk summary"

    agent.run = AsyncMock(
        side_effect=[
            mock_chunk_result,
            mock_chunk_result,
            Exception("Consolidation failed"),
        ]
    )

    with pytest.raises(Exception, match="Consolidation failed"):
        await summarize_long_text("A" * 500, agent, limiter, 100)


@pytest.mark.asyncio
async def test_find_best_effort_split_complex():
    """Test find_best_effort_split with mixed tool pairs."""
    from zrb.llm.summarizer.history_splitter import find_best_effort_split

    limiter = MockLimiter()

    # 1. Complete pair (must not break)
    # 2. Call without return (can break)
    # 3. Orphaned return (can break)

    messages = [
        ModelRequest(
            parts=[ToolCallPart(tool_name="complete", args={}, tool_call_id="c1")]
        ),  # 0
        ModelResponse(parts=[TextPart(content="Working...")]),  # 1
        ModelRequest(
            parts=[
                ToolReturnPart(content="done", tool_name="complete", tool_call_id="c1")
            ]
        ),  # 2
        ModelRequest(
            parts=[ToolCallPart(tool_name="incomplete", args={}, tool_call_id="i1")]
        ),  # 3
        ModelRequest(parts=[UserPromptPart(content="last message")]),  # 4
    ]

    # Try to keep as much as possible but under 50 tokens
    # Each message is 1000 tokens in MockLimiter list mode if not string
    # Let's fix MockLimiter to be more predictable for this test
    class PreciseLimiter:
        def count_tokens(self, content):
            if isinstance(content, str):
                return len(content)
            if isinstance(content, list):
                return sum(self.count_tokens(m) for m in content)
            return 10

        def truncate_text(self, text, limit):
            return text[:limit]

    # Threshold 25 tokens -> can keep 2 messages (20 tokens)
    # Split at index 3 keeps [3, 4] -> "incomplete" call + "last message"
    # This is safe because "complete" pair is [0, 2] and it's entirely in summarized part

    to_sum, to_keep = find_best_effort_split(messages, PreciseLimiter(), 25)
    assert len(to_keep) >= 1
    assert messages[-1] in to_keep


def test_validate_tool_pair_integrity_problems():
    """Test validate_tool_pair_integrity with problematic history."""
    from zrb.llm.message import validate_tool_pair_integrity

    # 1. Call without return
    messages = [
        ModelRequest(parts=[ToolCallPart(tool_name="t", args={}, tool_call_id="c1")])
    ]
    is_valid, problems = validate_tool_pair_integrity(messages)
    assert not is_valid
    assert any("has no return" in p for p in problems)

    # 2. Return without call
    messages = [
        ModelRequest(
            parts=[ToolReturnPart(content="r", tool_name="t", tool_call_id="c2")]
        )
    ]
    is_valid, problems = validate_tool_pair_integrity(messages)
    assert not is_valid
    assert any("has no call" in p for p in problems)
