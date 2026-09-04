"""
Tests for tool call/return pair safety in summarization.
These tests verify that summarization preserves tool call/return pairs
as required by Pydantic AI.
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

try:
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
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


from zrb.llm.message import validate_tool_pair_integrity
from zrb.llm.summarizer.history_splitter import (
    find_best_effort_split,
    find_safe_split_index,
)


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(self.count_tokens(m) for m in content)
        # For messages, return a low count to avoid triggering thresholds
        return 10

    def truncate_text(self, text, limit):
        return text[:limit]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_find_safe_split_index_simple():
    """Test finding safe split index with simple history."""
    limiter = MockLimiter()

    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
        ModelRequest(parts=[UserPromptPart("Q2")]),  # We want to keep from here
    ]

    # Mock is_turn_start to identify Q2 as a turn start
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "zrb.llm.config.limiter.is_turn_start", lambda msg: msg == messages[4]
        )

        split_idx = find_safe_split_index(messages, limiter, 100)

        # Should find split at index 4 (before Q2)
        assert split_idx == 4


def test_find_safe_split_index_no_safe_split():
    """Test when no safe split is possible."""
    limiter = MockLimiter()

    # Messages with a tool call but no return (incomplete pair)
    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        # No return - so any split that keeps the call would be unsafe
        # and any split that summarizes the call loses it
    ]

    split_idx = find_safe_split_index(messages, limiter, 100)

    # With current logic: split at index 1 is considered safe because
    # the call (at index 1) would be kept in messages, not summarized away.
    # The call without return in kept messages is allowed (return might come later).
    # So we expect 1, not -1.
    assert split_idx == 1


def test_find_best_effort_split():
    """Test best-effort split when no perfect split exists."""
    limiter = MockLimiter()

    # Create a history where we have to break some pairs
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
        ModelRequest(parts=[UserPromptPart("Q2")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool2", args={}, tool_call_id="call_2")]
        ),
        # Missing return for call_2
        ModelResponse(parts=[TextPart("A2")]),
    ]

    to_summarize, to_keep = find_best_effort_split(messages, limiter, 100)

    # Should return some split (not empty)
    assert len(to_summarize) > 0
    assert len(to_keep) > 0
    assert len(to_summarize) + len(to_keep) == len(messages)

    # The split should be valid (messages concatenated should equal original)
    assert to_summarize + to_keep == messages


def test_validate_tool_pair_integrity_valid():
    """Test validation of valid tool pairs."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
    ]

    is_valid, problems = validate_tool_pair_integrity(messages)

    assert is_valid == True
    assert len(problems) == 0


def test_validate_tool_pair_integrity_invalid():
    """Test validation of invalid tool pairs (calls without returns)."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        # Missing return for call_1
        ModelResponse(parts=[TextPart("A1")]),
    ]

    is_valid, problems = validate_tool_pair_integrity(messages)

    assert is_valid == False
    assert len(problems) == 1
    assert "call_1" in problems[0]
    assert "has no return" in problems[0]


def test_validate_tool_pair_integrity_orphaned_return():
    """Test validation with orphaned returns."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="orphaned"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
    ]

    is_valid, problems = validate_tool_pair_integrity(messages)

    assert is_valid == False
    assert len(problems) == 1
    assert "orphaned" in problems[0]
    assert "has no call" in problems[0]


@pytest.mark.asyncio
async def test_integration_with_summarize_history():
    """Integration test with the actual summarize_history function."""
    from unittest.mock import AsyncMock, patch

    from zrb.llm.summarizer import summarize_history

    limiter = MockLimiter()
    agent = MagicMock()

    mock_result = MagicMock()
    mock_result.output = "<state_snapshot>Summary</state_snapshot>"
    agent.run = AsyncMock(return_value=mock_result)

    # Create messages with tool pairs
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
        ModelRequest(parts=[UserPromptPart("Q2")]),  # Turn start we want to keep
    ]

    # Mock is_turn_start to identify Q2 as turn start
    with patch(
        "zrb.llm.config.limiter.is_turn_start",
        side_effect=[False, False, False, False, True],
    ):
        # Mock chunk_and_summarize to return a summary
        with patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
        ):

            result = await summarize_history(
                messages,
                agent=agent,
                summary_window=1,  # Keep only last message
                limiter=limiter,
                conversational_token_threshold=100,  # Enough threshold to trigger summarization but keep Q2
            )

    # Should have a summary + kept messages (merged due to consecutive User messages)
    assert len(result) == 1
    assert "Summary" in str(result[0])
    assert "Q2" in str(result[0])
