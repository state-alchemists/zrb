from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart
except ImportError:

    @dataclass
    class ToolReturnPart:
        content: Any
        tool_name: str = "test"
        tool_call_id: str = "123"

    @dataclass
    class ModelRequest:
        parts: list[Any] = field(default_factory=list)

    @dataclass
    class UserPromptPart:
        content: Any


from zrb.llm.history_processor.summarizer import create_summarizer_history_processor


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            # Account for some overhead in messages
            return len(content)
        if hasattr(content, "parts"):
            return sum(self.count_tokens(p) for p in content.parts)
        if hasattr(content, "content"):
            return self.count_tokens(content.content)
        if isinstance(content, list):
            return sum(self.count_tokens(i) for i in content)
        return len(str(content))

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_integration_dual_threshold_flow():
    # 1. Setup agents and limiter
    msg_agent = MagicMock()
    msg_agent.run = AsyncMock(return_value=MagicMock(output="Msg Summary"))

    conv_agent = MagicMock()
    conv_agent.run = AsyncMock(return_value=MagicMock(output="Conv Summary"))

    limiter = MockLimiter()

    # 2. Processor with dual thresholds
    # message_token_threshold = 50 (triggers fat msg summarization)
    # conversational_token_threshold = 200 (triggers history compression & insanity limit)
    processor = create_summarizer_history_processor(
        conversational_agent=conv_agent,
        message_agent=msg_agent,
        limiter=limiter,
        conversational_token_threshold=200,
        message_token_threshold=50,
        summary_window=2,
    )

    # 3. Create history with one "fat" message and one normal message
    # Fat message has 75 chars (> 50 msg threshold, < 200 conversational threshold)
    fat_msg = ModelRequest(
        parts=[ToolReturnPart(content="A" * 75, tool_name="t", tool_call_id="1")]
    )
    normal_msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    history = [fat_msg, normal_msg]

    # Total tokens = 75 + 5 = 80 (below 200 conversational threshold)

    with patch("zrb.llm.summarizer.message_processor.zrb_print"), patch(
        "zrb.llm.history_processor.summarizer.zrb_print"
    ):
        new_history = await processor(history)

    # EXPECTED:
    # - Fat message should be summarized because it's > 50
    # - Conversational summarization should NOT be triggered because 80 < 200
    assert len(new_history) == 2
    assert "SUMMARY" in new_history[0].parts[0].content
    assert "Msg Summary" in new_history[0].parts[0].content
    assert new_history[1] == normal_msg
    assert msg_agent.run.called
    assert not conv_agent.run.called

    # 4. Now test the "Insanity" trigger (message > conversational threshold)
    # Content of 300 chars (> 200 conversational threshold)
    insane_msg = ModelRequest(
        parts=[ToolReturnPart(content="B" * 300, tool_name="t", tool_call_id="2")]
    )
    history = [insane_msg]

    msg_agent.run.reset_mock()
    conv_agent.run.reset_mock()

    with patch(
        "zrb.llm.summarizer.message_processor.zrb_print"
    ) as mock_msg_print, patch("zrb.llm.history_processor.summarizer.zrb_print"):
        new_history = await processor(history)

    # EXPECTED:
    # - Truncation to 100 tokens (insanity limit) should be logged
    # - Summarization should still happen on the truncated content
    assert len(new_history) == 1
    assert "SUMMARY" in new_history[0].parts[0].content
    assert msg_agent.run.called

    # Check if insanity print was called
    printed_texts = [call.args[0] for call in mock_msg_print.call_args_list]
    assert any(
        "too large for efficient summarization" in text for text in printed_texts
    )
