from dataclasses import dataclass, field
from typing import Any, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock pydantic_ai if not available
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


from zrb.llm.history_processor.summarizer import (
    create_summarizer_history_processor,
    summarize_history,
    summarize_messages,
)
from zrb.llm.summarizer import (
    find_safe_split_index,
    message_to_text,
    model_request_to_text,
    model_response_to_text,
    process_message_for_summarization,
    process_tool_return_part,
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
async def test_summarize_fat_tool_results():
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Short summary"
    agent.run = AsyncMock(return_value=mock_result)

    # Message with a fat tool result (100 chars)
    fat_content = "A" * 100
    msg = ModelRequest(
        parts=[ToolReturnPart(content=fat_content, tool_name="test", tool_call_id="1")]
    )

    # Threshold 50
    new_messages = await summarize_messages(
        [msg], agent=agent, limiter=limiter, message_token_threshold=50
    )

    assert len(new_messages) == 1
    assert "SUMMARY of tool result:" in new_messages[0].parts[0].content
    assert "Short summary" in new_messages[0].parts[0].content


def test_message_to_text():
    req = ModelRequest(parts=[UserPromptPart(content="User input")])
    res = ModelResponse(parts=[TextPart(content="Model output")])

    assert "User: User input" in message_to_text(req)
    assert "AI: Model output" in message_to_text(res)
    assert "None" in message_to_text(None)


def test_model_request_to_text_complex():
    parts = [
        SystemPromptPart(content="Sys prompt"),
        UserPromptPart(content="Hello"),
        ToolReturnPart(content="Result", tool_name="calc", tool_call_id="1"),
        UserPromptPart(
            content=[
                "Multi-part",
                ImageUrl(url="http://img"),
                BinaryContent(data=b"bin", media_type="image/png"),
                AudioUrl(url="http://audio"),
                VideoUrl(url="http://video"),
                DocumentUrl(url="http://doc"),
                123,
            ]
        ),
    ]
    req = ModelRequest(parts=parts)
    text = model_request_to_text(req)
    assert "System: Sys prompt" in text
    assert "User: Hello" in text
    assert "Tool Result (calc): Result" in text
    assert "User: Multi-part" in text
    assert "[Image URL: http://img]" in text
    assert "[Binary Content: image/png]" in text
    assert "[Audio URL: http://audio]" in text
    assert "[Video URL: http://video]" in text
    assert "[Document URL: http://doc]" in text


def test_model_response_to_text_complex():
    parts = [
        TextPart(content="Thinking..."),
        ToolCallPart(tool_name="search", args={"q": "zrb"}, tool_call_id="2"),
        ToolReturnPart(
            content="Result in response", tool_name="extra", tool_call_id="3"
        ),
    ]
    res = ModelResponse(parts=parts)
    text = model_response_to_text(res)
    assert "AI: Thinking..." in text
    assert "AI Tool Call [2]: search({'q': 'zrb'})" in text
    assert "AI Tool Result (extra): Result in response" in text


@pytest.mark.asyncio
async def test_summarizer_early_exit():
    limiter = MockLimiter()
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    # Within limits
    # Since limiter returns 1000 for list, we need higher threshold
    result = await summarize_history(
        messages,
        limiter=limiter,
        summary_window=10,
        conversational_token_threshold=2000,
    )
    assert result == messages


@pytest.mark.asyncio
async def test_create_summarizer_history_processor_flow():
    limiter = MockLimiter()
    msg_agent = MagicMock()
    conv_agent = MagicMock()

    msg_result = MagicMock()
    msg_result.output = "msg summary"
    msg_agent.run = AsyncMock(return_value=msg_result)

    conv_result = MagicMock()
    conv_result.output = "conv summary"
    conv_agent.run = AsyncMock(return_value=conv_result)

    processor = create_summarizer_history_processor(
        conversational_agent=conv_agent,
        message_agent=msg_agent,
        limiter=limiter,
        conversational_token_threshold=10,
        message_token_threshold=30,
        summary_window=0,
    )

    messages = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="Very long tool result content to trigger agent",
                    tool_name="t",
                    tool_call_id="1",
                )
            ]
        ),
        ModelRequest(parts=[UserPromptPart(content="turn start")]),
        ModelRequest(parts=[UserPromptPart(content="active turn")]),
    ]

    with patch(
        "zrb.llm.config.limiter.is_turn_start",
        side_effect=[False, True, False],
    ):
        new_history = await processor(messages)

    # With summary_window=0 and token threshold exceeded, we should get a summary
    # and some kept messages.
    # Since the last kept message is a ModelRequest, it is merged with the summary message.
    assert len(new_history) == 1
    assert "Automated Context Restoration" in message_to_text(new_history[0])
    assert "active turn" in message_to_text(new_history[0])
    assert msg_agent.run.called
    assert conv_agent.run.called


@pytest.mark.asyncio
async def test_summarize_long_text_chunking():
    limiter = MockLimiter()
    agent = MagicMock()

    mock_result = MagicMock()
    mock_result.output = "Chunk summary"
    agent.run = AsyncMock(return_value=mock_result)

    # Text much longer than threshold
    long_text = "A" * 500
    summary = await summarize_long_text(long_text, agent, limiter, 100)

    assert "Chunk summary" in summary
    assert agent.run.call_count > 1


@pytest.mark.asyncio
async def test_summarize_history_with_multiple_snapshots():
    limiter = MockLimiter()
    agent = MagicMock()

    mock_result = MagicMock()
    mock_result.output = "Consolidated summary <state_snapshot>...</state_snapshot>"
    agent.run = AsyncMock(return_value=mock_result)

    messages = [
        ModelRequest(parts=[UserPromptPart(content="a" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="b" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="c" * 50)]),
    ]

    with patch("zrb.llm.config.limiter.is_turn_start", return_value=True):
        with patch(
            "zrb.llm.summarizer.chunk_processor.chunk_and_summarize",
            return_value="<state_snapshot>1</state_snapshot> <state_snapshot>2</state_snapshot>",
        ):
            new_history = await summarize_history(
                messages,
                agent=agent,
                summary_window=0,
                limiter=limiter,
                conversational_token_threshold=100,
            )

    assert len(new_history) <= 3
    assert any("<state_snapshot>" in message_to_text(m) for m in new_history)


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
    part = ToolReturnPart(content="SUMMARY of tool result: ...", tool_name="t")
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
    # - find_best_effort_split will find a split that keeps the last message
    # So we get 2 messages: summary + last message
    assert len(new_history) == 2
    assert isinstance(new_history[0], ModelRequest)  # Summary
    assert new_history[1] == msg2  # Last message kept intact

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
    from zrb.llm.summarizer.history_splitter import validate_tool_pair_integrity

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


def test_model_request_to_text_media_parts():
    """Test model_request_to_text with various media parts."""
    from pydantic_ai.messages import (
        AudioUrl,
        BinaryContent,
        DocumentUrl,
        ImageUrl,
        ModelRequest,
        UserPromptPart,
        VideoUrl,
    )

    parts = [
        UserPromptPart(
            content=[
                ImageUrl(url="http://img"),
                BinaryContent(data=b"bin", media_type="image/png"),
                AudioUrl(url="http://audio"),
                VideoUrl(url="http://video"),
                DocumentUrl(url="http://doc"),
            ]
        )
    ]
    req = ModelRequest(parts=parts)
    text = message_to_text(req)
    assert "[Image URL: http://img]" in text
    assert "[Binary Content: image/png]" in text
    assert "[Audio URL: http://audio]" in text
    assert "[Video URL: http://video]" in text
    assert "[Document URL: http://doc]" in text


@pytest.mark.asyncio
async def test_consolidate_summaries_public():
    """Test consolidate_summaries public function."""
    from zrb.llm.summarizer.chunk_processor import consolidate_summaries

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "<state_snapshot>Consolidated</state_snapshot>"
    agent.run = AsyncMock(return_value=mock_result)

    result = await consolidate_summaries("Summary text", agent, 100, True)
    assert "Consolidated" in result
    assert agent.run.called


@pytest.mark.asyncio
async def test_summarize_text_with_snapshot():
    """Test summarize_text handles state_snapshot tags correctly."""
    from zrb.llm.summarizer.text_summarizer import summarize_text

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = (
        "Random text <state_snapshot>Important data</state_snapshot> more text"
    )
    agent.run = AsyncMock(return_value=mock_result)

    result = await summarize_text("history", agent)
    assert result == "<state_snapshot>Important data</state_snapshot>"
