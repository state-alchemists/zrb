"""Shortening a long reply for the ear: the small model's summary is spoken
instead of the reply, which stays on screen in full.

A model that is slow, unavailable or unhelpful raises `SpeechSummaryError`, and
the caller reads the reply whole, as it would be with summarizing off.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.speech.text import clean_for_speech

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model


def create_speech_summarizer_agent(
    model: "str | Model | None" = None,
) -> "Agent[None, str]":
    """The summarizer, with the system prompt a project may override
    (`get_prompt("speech_summarizer")`). *model* defaults to the small model."""
    # lazy: heavy third-party — building an agent pulls in pydantic_ai.
    from zrb.llm.agent.common import create_agent

    return create_agent(
        model=resolve_configured_small_model(model),
        system_prompt=get_prompt("speech_summarizer"),
        # Already resolved here; resolve_model=False avoids resolving twice
        # inside create_agent.
        resolve_model=False,
    )


class SpeechSummaryError(Exception):
    """The model could not give a shorter summary in time."""


async def summarize_for_speech(
    text: str, model: "str | Model | None" = None, timeout: float = 0
) -> str:
    """A spoken summary of *text*, shorter than it. Raises `SpeechSummaryError`
    when the model fails, takes longer than *timeout* seconds (0: no limit), or
    gives back nothing or something no shorter, so the caller can read *text*
    whole."""
    try:
        agent = create_speech_summarizer_agent(model)
        result = await asyncio.wait_for(agent.run(text), timeout or None)
    except Exception as exc:
        raise SpeechSummaryError(str(exc) or type(exc).__name__) from exc
    summary = clean_for_speech(str(result.output or ""))
    if not summary or len(summary) >= len(text):
        raise SpeechSummaryError(
            "the model returned a summary that is empty or no shorter than the reply"
        )
    return summary
