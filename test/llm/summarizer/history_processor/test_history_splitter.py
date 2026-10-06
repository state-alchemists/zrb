from unittest.mock import patch

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.message import get_tool_pairs
from zrb.llm.summarizer.history_splitter import is_split_safe, split_history


class MockLimiter:
    def __init__(self, token_per_msg=10):
        self.token_per_msg = token_per_msg

    def count_tokens(self, content):
        if isinstance(content, list):
            return len(content) * self.token_per_msg
        return self.token_per_msg

    def truncate_text(self, text, limit):
        return text[:limit]


def test_get_tool_pairs_complex():
    messages: list[ModelMessage] = [
        ModelResponse(parts=[ToolCallPart(tool_name="t1", args={}, tool_call_id="c1")]),
        ModelRequest(
            parts=[ToolReturnPart(content="r1", tool_name="t1", tool_call_id="c1")]
        ),
        ModelRequest(
            parts=[ToolReturnPart(content="r2", tool_name="t2", tool_call_id="c2")]
        ),
        ModelRequest(
            parts=[ToolCallPart(tool_name="t3", args={}, tool_call_id="c3")]
        ),
    ]
    pairs = get_tool_pairs(messages)
    assert pairs["c1"]["call_idx"] == 0
    assert pairs["c1"]["return_idx"] == 1
    assert pairs["c2"]["call_idx"] is None
    assert pairs["c2"]["return_idx"] == 2
    assert pairs["c3"]["call_idx"] == 3
    assert pairs["c3"]["return_idx"] is None


def test_is_split_safe():
    messages: list[ModelMessage] = [
        ModelResponse(parts=[ToolCallPart(tool_name="t1", args={}, tool_call_id="c1")]),
        ModelRequest(
            parts=[ToolReturnPart(content="r1", tool_name="t1", tool_call_id="c1")]
        ),
    ]
    pairs = get_tool_pairs(messages)

    assert not is_split_safe(messages, 1, pairs)

    assert is_split_safe(messages, 0, pairs)
    assert is_split_safe(messages, 2, pairs)


@pytest.mark.asyncio
async def test_split_history_token_limit_trigger():
    limiter = MockLimiter(token_per_msg=100)
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="m1")]),
        ModelRequest(parts=[UserPromptPart(content="m2")]),
        ModelRequest(parts=[UserPromptPart(content="m3")]),
        ModelRequest(parts=[UserPromptPart(content="m4")]),
    ]




    with patch("zrb.llm.summarizer.history_splitter.is_turn_start", return_value=True):
        to_sum, to_keep = split_history(
            messages,
            summary_window=10,
            limiter=limiter,
            conversational_token_threshold=100,
        )








    assert len(to_keep) < 4


@pytest.mark.asyncio
async def test_split_history_fallback():
    limiter = MockLimiter(token_per_msg=10)
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="m1")]),
        ModelRequest(parts=[UserPromptPart(content="m2")]),
    ]

    with patch("zrb.llm.summarizer.history_splitter.is_turn_start", return_value=False):
        to_sum, to_keep = split_history(messages, 10, limiter, 100)

        assert len(to_keep) == 2
