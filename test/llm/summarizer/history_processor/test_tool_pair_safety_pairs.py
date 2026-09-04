"""
Tests for tool call/return pair safety in summarization.
These tests verify that summarization preserves tool call/return pairs
as required by Pydantic AI.
"""

from dataclasses import dataclass, field
from typing import Any

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


from zrb.llm.message import get_tool_pairs
from zrb.llm.summarizer.history_splitter import is_split_safe

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_get_tool_pairs_basic():
    """Test basic tool pair detection."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelResponse(
            parts=[
                TextPart("I'll check"),
                ToolCallPart(
                    tool_name="get_weather", args={"city": "NYC"}, tool_call_id="call_1"
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="Sunny", tool_name="get_weather", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("It's sunny")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    assert "call_1" in tool_pairs
    assert tool_pairs["call_1"]["call_idx"] == 1
    assert tool_pairs["call_1"]["return_idx"] == 2
    assert len(tool_pairs) == 1


def test_get_tool_pairs_multiple():
    """Test detection of multiple tool pairs."""
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
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result2", tool_name="tool2", tool_call_id="call_2"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A2")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    assert "call_1" in tool_pairs
    assert tool_pairs["call_1"]["call_idx"] == 1
    assert tool_pairs["call_1"]["return_idx"] == 2

    assert "call_2" in tool_pairs
    assert tool_pairs["call_2"]["call_idx"] == 5
    assert tool_pairs["call_2"]["return_idx"] == 6

    assert len(tool_pairs) == 2


def test_get_tool_pairs_orphaned_return():
    """Test detection of orphaned returns (returns without calls)."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result", tool_name="tool1", tool_call_id="orphaned"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("Response")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    assert "orphaned" in tool_pairs
    assert tool_pairs["orphaned"]["call_idx"] is None
    assert tool_pairs["orphaned"]["return_idx"] == 1


def test_get_tool_pairs_call_without_return():
    """Test detection of calls without returns (incomplete pairs)."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        # No return for call_1
        ModelResponse(parts=[TextPart("Still waiting...")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    assert "call_1" in tool_pairs
    assert tool_pairs["call_1"]["call_idx"] == 1
    assert tool_pairs["call_1"]["return_idx"] is None


def test_is_split_safe_complete_pair():
    """Test that complete tool pairs can be kept together."""
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

    tool_pairs = get_tool_pairs(messages)

    # Split after the complete pair (index 3) - should be safe
    assert is_split_safe(messages, 3, tool_pairs) == True

    # Split between call and return (index 2) - should be unsafe
    assert is_split_safe(messages, 2, tool_pairs) == False


def test_is_split_safe_multiple_pairs():
    """Test safety with multiple tool pairs."""
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
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result2", tool_name="tool2", tool_call_id="call_2"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A2")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    # Split between the two pairs (index 4) - should be safe
    assert is_split_safe(messages, 4, tool_pairs) == True

    # Split in the middle of second pair (index 6) - should be unsafe
    assert is_split_safe(messages, 6, tool_pairs) == False


def test_is_split_safe_orphaned_return():
    """Test that orphaned returns don't prevent splitting."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result", tool_name="tool1", tool_call_id="orphaned"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("Response")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    # Split before orphaned return (index 1) - should NOT be safe (orphaned returns MUST be summarized/removed)
    assert is_split_safe(messages, 1, tool_pairs) == False

    # Split after orphaned return (index 2) - should be safe
    assert is_split_safe(messages, 2, tool_pairs) == True


def test_is_split_safe_call_without_return():
    """Test safety with calls that don't have returns yet."""
    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        # No return yet
        ModelResponse(parts=[TextPart("Waiting...")]),
    ]

    tool_pairs = get_tool_pairs(messages)

    # Split before the call (index 1) - should be safe (call stays in kept messages)
    assert is_split_safe(messages, 1, tool_pairs) == True

    # Split after the call (index 2) - should be safe (call is before split)
    assert (
        is_split_safe(messages, 2, tool_pairs) == False
    )  # Call would be summarized away
