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
    create_summarizer_history_processor,
    message_to_text,
    model_request_to_text,
    model_response_to_text,
    summarize_history,
    summarize_long_text,
    summarize_messages,
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
    assert "SUMMARY OF TOOL RESULT:" in new_messages[0].parts[0].content
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
async def test_summarizer_does_not_skip_when_to_summarize_tokens_exceed_threshold():
    # Regression test: the early-return guard compared len(to_summarize) (message count)
    # against 0.3 * conversational_token_threshold (a token count), which made it almost
    # always True and silently skipped conversational summarization. It should compare
    # the TOKEN COUNT of to_summarize instead.
    #
    # Setup:
    #   conversational_token_threshold = 100  →  0.3 * 100 = 30
    #   summary_window = 1 (keep 1 msg, summarize the rest)
    #   5 messages × 8 chars each = 40 total tokens  →  is_within_tokens = True
    #   to_summarize = first 4 messages = 32 tokens  >  30
    #   Old bug: len(to_summarize)=4 < 30 → early return (wrong)
    #   Fixed:   count_tokens(to_summarize)=32 > 30 → proceeds to summarize (correct)
    limiter = MockLimiter()
    content = "x" * 8  # 8 tokens each per MockLimiter
    messages = [
        ModelRequest(parts=[UserPromptPart(content=content)]),
        ModelRequest(parts=[UserPromptPart(content=content)]),
        ModelRequest(parts=[UserPromptPart(content=content)]),
        ModelRequest(parts=[UserPromptPart(content=content)]),
        ModelRequest(parts=[UserPromptPart(content=content)]),
    ]

    agent = MagicMock()
    agent_result = MagicMock()
    agent_result.output = "summary text"
    agent.run = AsyncMock(return_value=agent_result)

    result = await summarize_history(
        messages,
        agent=agent,
        limiter=limiter,
        summary_window=1,
        conversational_token_threshold=100,
    )

    # Summarization must have run: result is compressed, not the original list
    assert result != messages
    assert agent.run.called


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

    # With summary_window=0 and token threshold exceeded, we should get a summary.
    # Since no safe split is found (mock limiter returns high token count),
    # it falls back to summarizing everything.
    assert len(new_history) == 1
    assert "Automated Context Restoration" in message_to_text(new_history[0])
    # The active turn is summarized into "conv summary". With the artificially
    # tiny threshold (10) and MockLimiter (1 char == 1 token), the consolidation
    # step truncates that summary to the threshold using the SAME limiter that
    # was threaded through summarize_history — so the surviving prefix is
    # "conv summa". (Before consolidate_summaries accepted a limiter argument it
    # silently used the lenient default singleton and left the text untruncated.)
    assert "conv summa" in message_to_text(new_history[0])
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
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
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
async def test_summarize_history_bakes_journal_index_into_summary():
    """When a journal index exists, summarization re-seeds it into the summary."""
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "summary text"
    agent.run = AsyncMock(return_value=mock_result)

    messages = [
        ModelRequest(parts=[UserPromptPart(content="a" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="b" * 50)]),
    ]

    journal_block = "<journal-index>\nMy Hub\n</journal-index>"
    with (
        patch("zrb.llm.config.limiter.is_turn_start", return_value=True),
        patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            return_value="old conversation summary",
        ),
        patch(
            "zrb.llm.summarizer.history_summarizer.render_journal_index",
            return_value=journal_block,
        ),
    ):
        new_history = await summarize_history(
            messages, agent=agent, limiter=limiter, force=True
        )

    assert any("<journal-index>" in message_to_text(m) for m in new_history)
    assert any("My Hub" in message_to_text(m) for m in new_history)


@pytest.mark.asyncio
async def test_summarize_history_without_journal_index_is_unaffected():
    """No journal index → summary is produced without a journal block."""
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "summary text"
    agent.run = AsyncMock(return_value=mock_result)

    messages = [ModelRequest(parts=[UserPromptPart(content="a" * 50)])]

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

    assert not any("<journal-index>" in message_to_text(m) for m in new_history)
