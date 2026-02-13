from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from zrb.llm.history_processor.summarizer import summarize_history


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content)
        # Always return high count for non-strings (messages list) to trigger threshold
        return 1000

    def truncate_text(self, text, limit):
        return text[:limit]


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
    # Since limiter returns 1000, it is > 10.
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
