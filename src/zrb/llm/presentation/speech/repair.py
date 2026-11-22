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
from concurrent.futures import ThreadPoolExecutor
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

#: Every repair in the process shares this one worker. A repair cannot be taken
#: back once it has started — a provider that never answers keeps its thread
#: until the process ends — so the ceiling is what keeps one stuck provider from
#: eating the loop's own executor, where unrelated work runs. The reply that
#: needs a repair while this is busy is read whole, on its own deadline.
_REPAIR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="speech-repair")


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
    text: str,
    model: "str | Model | None" = None,
    timeout: float = 0,
    repairer: "SpeechRepairer | None" = None,
) -> RepairedSpeech:
    """The line to speak instead of *text*. Raises `SpeechRepairError` when the
    model fails, takes longer than *timeout* seconds (0: no limit), or answers
    with nothing for the ear.

    *timeout* bounds the wait from outside the call, not at an ``await``: the
    agent is built and run in a worker thread, so a resolver that blocks before
    its first ``await`` — initializing a local model, waiting in provider setup
    — holds that thread and not the event loop, and the deadline still fires.
    The worker is then abandoned and its late line dropped: the caller has
    already fallen back to reading the reply whole.

    *repairer* is the one a session holds, which runs one repair at a time; on
    its own this call gets a fresh one and so serializes with nothing."""
    try:
        return await (repairer or SpeechRepairer()).repair(text, model, timeout)
    except SpeechRepairError:
        raise
    except Exception as exc:
        raise SpeechRepairError(str(exc) or type(exc).__name__) from exc


class SpeechRepairer:
    """One repair at a time, for one session.

    A deadline bounds the *wait*, not the call. A worker that outlives it keeps
    running until the model answers or the process ends, so starting another
    beside it is how one stuck provider would take two of whatever runs them.
    While a worker is alive the next reply is read whole, which is the outcome
    it had before the repair existed, so a session never has more than one.
    That worker is not the loop's default executor, which the rest of the
    process runs unrelated work on; repairs share `_REPAIR_EXECUTOR`, one
    thread for the whole process, so a provider that never answers costs a
    later reply its line and nothing else.

    The work runs on a thread whether or not there is a deadline: the model is
    resolved and the agent built before the first `await`, and that is precisely
    the code that can block the loop.
    """

    def __init__(self) -> None:
        self._outstanding: "asyncio.Future[RepairedSpeech] | None" = None

    async def repair(
        self, text: str, model: "str | Model | None" = None, timeout: float = 0
    ) -> RepairedSpeech:
        if self._outstanding is not None and not self._outstanding.done():
            raise SpeechRepairError(
                "an earlier repair is still running, so this reply is read whole"
            )
        worker = _start(text, model)
        self._outstanding = worker
        if not timeout:
            return await worker
        # `wait` rather than `wait_for`: cancelling the future cancels nothing
        # in a thread that already started, and the line is dropped either way.
        done, _ = await asyncio.wait({worker}, timeout=timeout)
        if not done:
            raise SpeechRepairError(
                f"the model gave no line within {timeout:g}s, so the reply is read whole"
            )
        return worker.result()


def _start(text: str, model: "str | Model | None") -> "asyncio.Future[RepairedSpeech]":
    """Start one repair on the repair executor, carrying the caller's context.

    Not `run_in_executor(None, …)`: that puts the worker in the loop's default
    pool, which `asyncio.to_thread` and the rest of the process also draw on,
    and a worker cannot be taken back once it has started — so a provider that
    never answers would hold a slot another job needs. `_REPAIR_EXECUTOR` has
    one worker for the whole process, which is the ceiling: a repair that is
    still stuck when the next reply needs one leaves that reply read whole,
    because its own deadline fires while it waits for the slot.
    """
    loop = asyncio.get_running_loop()
    # The context goes with it because the small model is chosen from
    # `ContextVar`s set by the run that is waiting for this line.
    context = contextvars.copy_context()
    outcome = _REPAIR_EXECUTOR.submit(_run_in_its_own_thread, context, text, model)
    worker: "asyncio.Future[RepairedSpeech]" = asyncio.wrap_future(outcome, loop=loop)
    # Its outcome is read here whether or not anyone waits for it any more, so a
    # dropped repair is not reported as an exception never retrieved.
    worker.add_done_callback(_drop)
    return worker


def _run_in_its_own_thread(
    context: "contextvars.Context", text: str, model: "str | Model | None"
) -> RepairedSpeech:
    """One repair on a thread of its own, under the caller's context.

    `asyncio.run` gives it a loop of its own, which is what a thread needs; the
    context is carried in because the model is chosen from `ContextVar`s set by
    the run that is waiting for it. Whatever it raises settles the future the
    executor handed back, so the loop is never left waiting for an answer.
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
