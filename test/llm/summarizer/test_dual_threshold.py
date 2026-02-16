from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.summarizer.message_processor import process_tool_return_part


@dataclass
class ToolReturnPart:
    content: Any
    tool_name: str = "test"
    tool_call_id: str = "123"


class MockLimiter:
    def count_tokens(self, content):
        if content is None:
            return 0
        return len(str(content))

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_process_tool_return_part_dual_thresholds():
    limiter = MockLimiter()
    agent = MagicMock()

    # 1. Below message threshold -> No change
    part = ToolReturnPart(content="12345")
    res, modified = await process_tool_return_part(
        part, agent, limiter, message_threshold=10, insanity_threshold=20
    )
    assert not modified
    assert res.content == "12345"

    # 2. Above message threshold, below insanity threshold -> Summarize
    msg_threshold = 50
    insanity_threshold = 100
    fat_content = "A" * 75  # 75 > 50 (msg) but < 100 (insanity)
    part = ToolReturnPart(content=fat_content)

    with patch(
        "zrb.llm.summarizer.text_summarizer.summarize_text_plain",
        AsyncMock(return_value="Short Summary"),
    ) as mock_sum:
        res, modified = await process_tool_return_part(
            part,
            agent,
            limiter,
            message_threshold=msg_threshold,
            insanity_threshold=insanity_threshold,
        )
        assert modified
        assert res.content == "SUMMARY of tool result:\nShort Summary"
        # Verify it was NOT truncated before summarization (passed 75 chars)
        called_content = mock_sum.call_args[0][0]
        assert len(called_content) == 75
        assert called_content == fat_content

    # 3. Above insanity threshold -> Truncate BEFORE summarize
    insane_content = "B" * 150  # 150 > 100 (insanity)
    part = ToolReturnPart(content=insane_content)

    with patch(
        "zrb.llm.summarizer.text_summarizer.summarize_text_plain",
        AsyncMock(return_value="Short Summary"),
    ) as mock_sum:
        res, modified = await process_tool_return_part(
            part,
            agent,
            limiter,
            message_threshold=msg_threshold,
            insanity_threshold=insanity_threshold,
        )
        assert modified
        # Verify it WAS truncated to insanity_threshold (100) before summarization
        called_content = mock_sum.call_args[0][0]
        assert len(called_content) == 100
        assert called_content == "B" * 100
