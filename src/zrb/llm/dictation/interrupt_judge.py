"""Asking the small model what the words said over zrb ask of it.

The word lists decide what is plain — "stop", "stop please", "wait" — and they
are free. Everything else ("please fucking stop", the same phrase said twice,
another language, "shut up") reads as a request to anyone but a substring
match, and reaches a small model instead, whose answer is a typed
`BargeInVerdict` rather than a phrase zrb has to re-parse.

A model that is slow, unavailable or unparseable costs nothing: the caller
keeps the answer the word lists already gave (`DictationSession` and
`words.is_said_alone`), which is what zrb did before there was a judge.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)

#: How long the judge may take before the word lists decide instead. Long
#: enough for a small model on a slow link, short enough that zrb's voice is
#: not held on it: a stop worth making arrives while the user is still talking,
#: and the words are only transcribed after they stop.
_JUDGE_TIMEOUT_SECONDS = 2.0


class BargeInVerdict(BaseModel):
    """What the words heard over zrb ask of it."""

    intent: Literal["stop", "ask"]
    """``stop``: be quiet and cancel the turn. ``ask``: it is a request; the
    turn goes on and takes it into account."""

    reason: str = ""
    """Why, in a few words: logged, and shown to no one."""


def create_interrupt_judge_agent(
    model: "str | Model | None" = None,
    system_prompt: str | None = None,
) -> "Agent[None, BargeInVerdict]":
    """The judge, with the system prompt a project may override
    (`get_prompt("barge_in")`, like every other internal agent prompt)."""
    # lazy: heavy third-party — building an agent pulls in pydantic_ai.
    from zrb.llm.agent.common import create_agent

    return create_agent(
        model=resolve_configured_small_model(model),
        system_prompt=system_prompt or get_prompt("barge_in"),
        output_type=BargeInVerdict,
        # Already resolved here; resolve_model=False avoids resolving twice
        # inside create_agent.
        resolve_model=False,
    )


async def judge_barge_in(
    command: str, model: "str | Model | None" = None
) -> BargeInVerdict | None:
    """What *command* — what was heard over zrb, past its wake word — asks of
    it, or ``None`` when the judge could not answer in time, is not configured
    to work, or failed. Never raises: an interrupting utterance is not worth
    ending a session's listening over."""
    # lazy: heavy third-party — pydantic_ai, and its exceptions with it.
    from pydantic_ai.exceptions import AgentRunError, UserError

    try:
        agent = create_interrupt_judge_agent(model)
        result = await asyncio.wait_for(
            agent.run(command), _JUDGE_TIMEOUT_SECONDS
        )
        return result.output
    except (AgentRunError, UserError, asyncio.TimeoutError, OSError) as exc:
        logger.warning(f"Deciding what {command!r} asks of zrb failed: {exc}")
        return None
