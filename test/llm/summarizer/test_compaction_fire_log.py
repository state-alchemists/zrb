"""A compaction says why it fired: in the log, and on its usage record.

Three different things start a compaction, and the tokens a usage line carries
cannot tell them apart: the token trigger compares the history against the
configured threshold *less the system prompt*, the message window fires on
count alone, and `/compress` fires on neither. These tests pin what the fire
line says, and that a fire which reached no model does not disappear from
`/usage` without a word. They drive the public processor and summarizer, so
nothing here reaches a private helper.
"""

import logging
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.shared.usage_log import LIMIT_TOKEN, CompactionDetail
from zrb.llm.summarizer import history_summarizer


class FixedLimiter(LLMLimiter):
    """Every message costs the same, so a threshold is easy to predict."""

    def __init__(self, per_message: int = 10):
        super().__init__()
        self.per_message = per_message

    def count_tokens(self, content) -> int:
        if isinstance(content, list):
            return len(content) * self.per_message
        return self.per_message

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text


def _turns(count: int):
    """`count` question/answer pairs, two messages each."""
    messages = []
    for i in range(count):
        messages.append(ModelRequest(parts=[UserPromptPart(content=f"question {i}")]))
        messages.append(ModelResponse(parts=[TextPart(content=f"answer {i}")]))
    return messages


def _processor(limiter, conversational_token_threshold: int):
    """The seam the chat path uses, so a test fires the trigger as a run does."""
    return history_summarizer.create_summarizer_history_processor(
        conversational_agent=MagicMock(),
        message_agent=MagicMock(),
        limiter=limiter,
        conversational_token_threshold=conversational_token_threshold,
        summary_window=300,
    )


async def _keep(messages, **kwargs):
    return messages


@pytest.mark.asyncio
async def test_a_compaction_fire_records_the_trigger_and_the_prompt(
    caplog, monkeypatch
):
    """The fire line is the only record of what the trigger saw.

    The usage log counts the summary call, which is chunked and so smaller than
    the history; the verbatim header counts only the messages the summary
    replaced. Neither says which limit was reached, nor how much of the trigger
    the system prompt had already spent — so the fire itself has to say both.
    """
    monkeypatch.setattr(history_summarizer, "summarize_history", _keep)

    with caplog.at_level(logging.WARNING):
        await _processor(FixedLimiter(per_message=10), 100)(
            _turns(6),  # 12 messages, 120 tokens at 10 each
            system_prompt_overhead=40,
        )

    (line,) = [
        record.getMessage()
        for record in caplog.records
        if "Compaction fired" in record.getMessage()
    ]
    assert "on the token limit" in line
    # The history, against what the prompt left of the trigger — not the trigger.
    assert "120 tokens against 60 allowed" in line
    assert "100 trigger less a 40 system prompt" in line
    assert "12 messages against a 300 window" in line


@pytest.mark.asyncio
async def test_the_fire_line_names_the_message_window_when_tokens_fit(
    caplog, monkeypatch
):
    """The window can fire a compaction on its own, and the line has to say so.

    A reader who sees only a token figure would take a message-count fire for a
    mismeasurement, which is the reading that made the board ask for this line.
    """
    monkeypatch.setattr(history_summarizer, "summarize_history", _keep)

    with caplog.at_level(logging.WARNING):
        await _processor(FixedLimiter(per_message=1), 1_000)(
            _turns(400),  # 800 messages, 800 tokens at 1 each
            system_prompt_overhead=0,
        )

    (line,) = [
        record.getMessage()
        for record in caplog.records
        if "Compaction fired" in record.getMessage()
    ]
    assert "on the message limit" in line
    assert "800 messages against a 300 window" in line


@pytest.mark.asyncio
async def test_a_fire_that_reached_no_model_does_not_vanish_from_usage(caplog):
    """A fire the log announces must not disappear from `/usage` in silence.

    `record_totals` writes no line for a compaction that never called the model,
    so `/usage` lists nothing — and a reader comparing the two surfaces would
    take the missing line for a compaction that never fired. The silent case
    says which it was. A history with nothing to replace is that case: the
    split keeps it whole and the summarizer is never asked.
    """
    with caplog.at_level(logging.WARNING):
        kept = await history_summarizer.summarize_history(
            _turns(1),
            limiter=FixedLimiter(per_message=10),
            conversational_token_threshold=1_000,
            compaction=CompactionDetail(
                reason=LIMIT_TOKEN,
                history_tokens=120,
                allowed_tokens=60,
                prompt_tokens=40,
                messages=12,
                window=300,
            ),
        )

    assert len(kept) == 2, "the history was replaced, so there was a call to record"
    said = [entry.getMessage() for entry in caplog.records]
    (line,) = [text for text in said if "reached no model" in text]
    assert "no usage line" in line
    assert "2 messages were left as they were" in line
