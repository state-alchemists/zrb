from unittest.mock import patch

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

from zrb.llm.summarizer.history_splitter import split_history


class MockLimiter:
    def __init__(self, token_per_msg=10):
        self.token_per_msg = token_per_msg

    def count_tokens(self, content):
        if isinstance(content, list):
            return len(content) * self.token_per_msg
        return self.token_per_msg

    def truncate_text(self, text, limit):
        return text[:limit]


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
