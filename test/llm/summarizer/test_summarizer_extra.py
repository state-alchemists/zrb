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

from zrb.llm.summarizer.history_splitter import (
    find_best_effort_split,
    find_safe_split_index,
    get_split_index,
    get_tool_pairs,
    is_split_safe,
    validate_tool_pair_integrity,
)
from zrb.llm.summarizer.history_summarizer import (
    create_summarizer_history_processor,
    summarize_history,
    summarize_messages,
)
from zrb.llm.summarizer.message_converter import message_to_text
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
            # Return a value that depends on content to avoid short-circuiting logic
            # but keep it simple.
            return sum(self.count_tokens(m) for m in content)
        if hasattr(content, "parts"):
            return 10
        return 1

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_get_split_index_empty():
    assert get_split_index([], 1) == -1


@pytest.mark.asyncio
async def test_summarize_messages_exception():
    messages = ["invalid message object"]
    result = await summarize_messages(messages)
    assert result == messages


@pytest.mark.asyncio
async def test_summarize_history_exception():
    limiter = MockLimiter()
    result = await summarize_history(None, limiter=limiter)
    assert result is None


@pytest.mark.asyncio
async def test_validate_tool_pair_integrity_edge_cases():
    class BadMsg:
        pass

    is_valid, problems = validate_tool_pair_integrity([BadMsg()])
    assert is_valid == True

    msg = ModelResponse(parts=[ToolCallPart(tool_name="t", args={}, tool_call_id="1")])
    del msg.parts[0].tool_call_id
    is_valid, problems = validate_tool_pair_integrity([msg])
    assert is_valid == True


@pytest.mark.asyncio
async def test_find_best_effort_split_no_messages():
    limiter = MockLimiter()
    to_sum, to_keep = find_best_effort_split([], limiter, 100)
    assert to_sum == []
    assert to_keep == []


@pytest.mark.asyncio
async def test_message_to_text_unexpected_type():
    assert message_to_text("not a message") == "not a message"


@pytest.mark.asyncio
async def test_summarize_text_plain_edge_cases():
    limiter = MockLimiter()
    agent = MagicMock()
    assert (
        await summarize_text_plain("text", agent, limiter, 0)
        == "[Threshold too low for summarization]"
    )
    assert await summarize_text_plain(123, agent, limiter, 100) == "123"


@pytest.mark.asyncio
async def test_summarize_text_with_snapshot_extraction():
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = (
        "Random text <state_snapshot>Actual Snapshot</state_snapshot> more text"
    )
    agent.run = AsyncMock(return_value=mock_result)

    result = await summarize_text("history", agent)
    assert result == "<state_snapshot>Actual Snapshot</state_snapshot>"


@pytest.mark.asyncio
async def test_summarize_history_no_summarize():
    limiter = MockLimiter()
    messages = [ModelRequest(parts=[UserPromptPart("hi")])]
    with patch(
        "zrb.llm.summarizer.history_summarizer.split_history",
        return_value=([], messages),
    ):
        result = await summarize_history(messages, limiter=limiter)
        assert result == messages


@pytest.mark.asyncio
async def test_summarize_long_text_depth_limit():
    limiter = MockLimiter()
    agent = MagicMock()
    result = await summarize_long_text("Very long text", agent, limiter, 5, depth=6)
    assert result == "Very "


@pytest.mark.asyncio
async def test_chunk_and_summarize_exception():
    from zrb.llm.summarizer.chunk_processor import chunk_and_summarize

    limiter = MockLimiter()
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=Exception("Agent error"))

    messages = [ModelRequest(parts=[UserPromptPart("hi")])]
    with pytest.raises(Exception):
        await chunk_and_summarize(messages, agent, limiter, 100)


@pytest.mark.asyncio
async def test_create_summarizer_history_processor_exception_path():
    limiter = MockLimiter()
    processor = create_summarizer_history_processor(
        limiter=limiter, conversational_token_threshold=10
    )
    with patch.object(limiter, "count_tokens", side_effect=Exception("Count error")):
        messages = [ModelRequest(parts=[UserPromptPart("hi")])]
        result = await processor(messages)
        assert result == messages
