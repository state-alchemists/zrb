from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from zrb.llm.summarizer import summarize_history


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content)
        if hasattr(content, "parts"):
            return 10
        if isinstance(content, list):
            return len(content) * 10
        return 0

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_summarize_history_consecutive_user_messages():
    limiter = MockLimiter()
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Summary content"
    agent.run = AsyncMock(return_value=mock_result)



    m1 = ModelRequest(parts=[UserPromptPart(content="User 1")])
    m2 = ModelResponse(parts=[TextPart(content="AI 1")])
    m3 = ModelRequest(parts=[UserPromptPart(content="User 2")])
    m4 = ModelResponse(parts=[TextPart(content="AI 2")])
    messages = [m1, m2, m3, m4]





    from zrb.llm.config.limiter import is_turn_start

    with patch(
        "zrb.llm.summarizer.history_splitter.is_turn_start", side_effect=is_turn_start
    ):
        new_history = await summarize_history(
            messages,
            agent=agent,
            summary_window=2,
            limiter=limiter,
            conversational_token_threshold=30,
        )


    assert len(new_history) == 2
    assert isinstance(new_history[0], ModelRequest)
    assert isinstance(new_history[1], ModelResponse)




    assert len(new_history[0].parts) == 3
    first_contents = [str(getattr(p, "content", "")) for p in new_history[0].parts]
    assert any("SYSTEM: Automated Context Restoration" in c for c in first_contents)
    assert any("User 1" in c for c in first_contents)
    assert any("User 2" in c for c in first_contents)


    second_contents = [str(getattr(p, "content", "")) for p in new_history[1].parts]
    assert any("AI 2" in c for c in second_contents)
