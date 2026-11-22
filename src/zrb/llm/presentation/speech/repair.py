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
import contextvars
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
    with nothing for the ear.

    *timeout* bounds the wait from outside the call, not at an ``await``: the
    agent is built and run in a worker thread, so a resolver that blocks before
    its first ``await`` — initializing a local model, waiting in provider setup
    — holds that thread and not the event loop, and the deadline still fires.
    The worker is then abandoned and its late line dropped: the caller has
    already fallen back to reading the reply whole."""
    try:
        return await _bounded(text, model, timeout)
    except SpeechRepairError:
        raise
    except Exception as exc:
        raise SpeechRepairError(str(exc) or type(exc).__name__) from exc


async def _bounded(
    text: str, model: "str | Model | None", timeout: float
) -> RepairedSpeech:
    if not timeout:
        return await _run(text, model)
    loop = asyncio.get_running_loop()
    # The worker's own context, as `SpeechSummarizer` does: the small model is
    # resolved from a `ContextVar` the run has set, and a bare thread would not
    # see it.
    context = contextvars.copy_context()
    worker = loop.run_in_executor(
        None, _run_in_its_own_thread, context, text, model
    )
    # `wait` rather than `wait_for`: cancelling the future would cancel nothing
    # in a thread that already started, and the answer is dropped either way.
    # The callback reads the late exception so asyncio does not report it as
    # never retrieved.
    worker.add_done_callback(_drop)
    done, _ = await asyncio.wait({worker}, timeout=timeout)
    if not done:
        raise SpeechRepairError(
            f"the model gave no line within {timeout:g}s, so the reply is read whole"
        )
    return worker.result()


def _run_in_its_own_thread(
    context: "contextvars.Context", text: str, model: "str | Model | None"
) -> RepairedSpeech:
    """One repair on a thread of its own, under the caller's context.

    `asyncio.run` gives it a loop of its own, which is what a thread needs; the
    context is carried in because the model is chosen from `ContextVar`s set by
    the run that is waiting for it.
    """
    return context.run(asyncio.run, _run(text, model))


def _drop(worker: "asyncio.Future[RepairedSpeech]") -> None:
    """Consume a worker's outcome that nobody is waiting for any more."""
    if not worker.cancelled():
        worker.exception()


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
