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


from zrb.llm.summarizer import message_to_text, summarize_history


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
    from zrb.llm.summarizer.text_summarizer import summarize_text_plain

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = (
        "Random text <state_snapshot>Important data</state_snapshot> more text"
    )
    agent.run = AsyncMock(return_value=mock_result)

    result = await summarize_text_plain("history", agent, MockLimiter(), 1000)
    assert "<state_snapshot>Important data</state_snapshot>" in result


@pytest.mark.asyncio
async def test_last_user_intent_instruction_injection():
    class MockInstructionLimiter:
        def count_tokens(self, content):
            if hasattr(content, "parts"):
                return 1000
            if isinstance(content, list):
                return 3000
            return len(str(content))

        def truncate_text(self, text, limit):
            return text[:limit]

    # Setup
    limiter = MockInstructionLimiter()
    agent = MagicMock()
    agent.last_prompt = None

    # Capture the prompt passed to agent
    mock_run = AsyncMock()

    async def side_effect(prompt):
        result = MagicMock()
        result.output = "Summary"
        agent.last_prompt = prompt
        return result

    mock_run.side_effect = side_effect
    agent.run = mock_run

    # Create messages
    messages = [
        ModelRequest(parts=[UserPromptPart(content="User message 1")]),
        ModelResponse(parts=[TextPart(content="AI message 1")]),
        ModelRequest(parts=[UserPromptPart(content="User message 2 - IMPORTANT")]),
    ]

    # Mock is_turn_start to prevent finding safe split
    # Mock validate_tool_pair_integrity to return True
    with patch("zrb.llm.config.limiter.is_turn_start", return_value=False):
        with patch(
            "zrb.llm.summarizer.history_summarizer.validate_tool_pair_integrity",
            return_value=(True, []),
        ):
            await summarize_history(
                messages,
                agent=agent,
                limiter=limiter,
                summary_window=0,
                conversational_token_threshold=500,
            )

    # Check if the instruction was added to ANY prompt passed to the agent
    found_instruction = False
    for call in agent.run.call_args_list:
        args, _ = call
        if args and isinstance(args[0], str):
            prompt = args[0]
            if (
                "IMPORTANT: The last part of this history contains the user's latest request"
                in prompt
            ):
                found_instruction = True
                break

    assert found_instruction, "Instruction not found in any agent call"
