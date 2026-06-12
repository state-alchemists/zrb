"""Tests for the rarely-hit branches in chunk_processor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.summarizer.chunk_processor import chunk_and_summarize


class _Limiter:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


@pytest.mark.asyncio
async def test_empty_messages_returns_no_summaries_marker():
    """No messages → no chunks → fall through to the [No summaries] sentinel."""
    out = await chunk_and_summarize(
        messages=[],
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=100,
    )
    assert "[No summaries generated]" in out


@pytest.mark.asyncio
async def test_message_to_text_failure_falls_back_to_str():
    """If message_to_text raises, the converter falls back to str(m) and
    summarization still runs end-to-end."""
    with (
        patch(
            "zrb.llm.summarizer.chunk_processor.message_to_text",
            side_effect=RuntimeError("bad message shape"),
        ),
        patch(
            "zrb.llm.summarizer.chunk_processor.summarize_text_plain",
            new=AsyncMock(return_value="SUMMARY"),
        ),
    ):
        out = await chunk_and_summarize(
            messages=["msg one", "msg two"],
            agent=MagicMock(),
            limiter=_Limiter(),
            token_threshold=100,
        )
    assert "SUMMARY" in out
