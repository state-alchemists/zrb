"""The line the ear should have had, for a reply that marked nothing.

A reply with no `<spoken>` block is read aloud in full — the fallback is never
silence — so a reply built around a table is heard as a table. Nothing prevents
that at the source: the rule is prose, and an output type cannot be required
without losing the streaming that speaks a reply while it is written (measured;
see issue #1004).

So the repair happens at the other end. When a reply is about to be read whole,
the small model is asked what the listener should have heard, and that line is
spoken instead. The reply on screen is untouched.

The answer is a structured one — `RepairedSpeech` — so the spoken line is a
field rather than a parse: a model returning nothing for the ear fails here
instead of reaching it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

from zrb.llm.contracts.config.model_resolver import resolve_configured_small_model
from zrb.llm.contracts.shared.prompt_text import get_prompt
from zrb.llm.contracts.shared.request_log import (
    REASON_SPEECH_REPAIR,
    record_standalone_requests,
)
from zrb.llm.contracts.shared.usage_log import (
    COMPONENT_SPEECH_REPAIR,
    record_agent_usage,
)

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)

# Longer than a spoken line has any business being, and short enough to notice
# a model that answered with the reply again. Not a limit on the reply.
_LONGEST_SPOKEN_LINE = 2000


class RepairedSpeech(BaseModel):
    """What the ear gets for a reply that marked nothing.

    *spoken* is the line itself. *emotion* names the voice it is said in and is
    optional: a model that leaves it empty gets the voice the reply's own
    leading emoji chose, which is what every other spoken text uses.
    """

    spoken: str
    emotion: str = ""


class SpeechRepairError(Exception):
    """The model gave no spoken line in time."""


def create_speech_repair_agent(
    model: "str | Model | None" = None,
) -> "Agent[None, RepairedSpeech]":
    """The repair agent, with the system prompt a project may override
    (`get_prompt("speech_repair")`). *model* defaults to the small model."""
    # lazy: heavy third-party — building an agent pulls in pydantic_ai.
    from zrb.llm.engine.agent.common import create_agent

    return create_agent(
        model=resolve_configured_small_model(model),
        system_prompt=get_prompt("speech_repair"),
        output_type=RepairedSpeech,
        # Already resolved here; resolve_model=False avoids resolving twice
        # inside create_agent.
        resolve_model=False,
    )


async def repair_for_speech(
    text: str, model: "str | Model | None" = None, timeout: float = 0
) -> RepairedSpeech:
    """The line to speak instead of *text*. Raises `SpeechRepairError` when the
    model fails, takes longer than *timeout* seconds (0: no limit), or answers
    with nothing for the ear. The timeout cancels the request only at an
    ``await``: it cannot interrupt a resolver that blocks while the agent is
    created."""
    try:
        return await asyncio.wait_for(_run(text, model), timeout or None)
    except SpeechRepairError:
        raise
    except Exception as exc:
        raise SpeechRepairError(str(exc) or type(exc).__name__) from exc


async def _run(text: str, model: "str | Model | None") -> RepairedSpeech:
    agent = create_speech_repair_agent(model)
    result = await agent.run(text)
    record_agent_usage(result, component=COMPONENT_SPEECH_REPAIR)
    record_standalone_requests(
        result, REASON_SPEECH_REPAIR, component=COMPONENT_SPEECH_REPAIR
    )
    output = result.output
    if not isinstance(output, RepairedSpeech):
        raise SpeechRepairError(
            f"the model answered with {type(output).__name__}, not a spoken line"
        )
    spoken = output.spoken.strip()
    if not spoken:
        raise SpeechRepairError(
            "the model answered with nothing for the ear, so the reply is read whole"
        )
    if len(spoken) > _LONGEST_SPOKEN_LINE:
        raise SpeechRepairError(
            f"the model returned {len(spoken)} characters for the ear, which is "
            "the reply again rather than a line"
        )
    return RepairedSpeech(spoken=spoken, emotion=output.emotion.strip())
