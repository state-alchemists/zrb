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
        return 10

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
    result = await summarize_history(
        messages, limiter=limiter, summary_window=10, conversational_token_threshold=100
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
    # and some kept messages. The exact number depends on the implementation.
    # Currently, it returns 2 messages: 1 summary + 1 kept message.
    assert len(new_history) == 2
    assert "Automated Context Restoration" in message_to_text(new_history[0])
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
                conversational_token_threshold=10,
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
    res = await process_message_for_summarization(msg, None, None, 10)
    assert res == msg


@pytest.mark.asyncio
async def test_process_tool_return_part_edge_cases():
    limiter = MockLimiter()
    # 1. Non-string content
    part = ToolReturnPart(content={"a": 1}, tool_name="t")
    res, mod = await process_tool_return_part(part, None, limiter, 10)
    assert mod is False

    # 2. Already summarized
    part = ToolReturnPart(content="SUMMARY of tool result: ...", tool_name="t")
    res, mod = await process_tool_return_part(part, None, limiter, 10)
    assert mod is False

    # 3. Low threshold (Warning path)
    part = ToolReturnPart(content="Very long content...", tool_name="t")
    res, mod = await process_tool_return_part(part, None, limiter, 5)
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
