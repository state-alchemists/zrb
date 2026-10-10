"""Shortening a long reply for the ear: the small model's summary is spoken
instead of the reply, which stays on screen in full.

A model that is slow, unavailable or unhelpful raises `SpeechSummaryError`, and
the caller reads the reply whole, as it would be with summarizing off.

Resolving the model cannot be cancelled once started. A resolution that outlasts
the timeout is abandoned on its daemon thread, and its result dropped when it
returns; `ResolutionSlot` keeps that to one stuck thread per session, until it
returns or the process exits.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
from collections.abc import Callable
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


class ResolutionSlot:
    """Room for one model resolution at a time.

    Resolving the model is a synchronous call that cannot be cancelled once
    started, so a timed-out one is abandoned on its thread and keeps running. A
    session holds one slot and a summary is refused while the previous
    resolution is still running, so a blocked resolver costs one thread until
    it returns (or the process exits), never one per reply.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self, target: Callable[[], None]) -> None:
        """Run *target* on a daemon thread, or raise `SpeechSummaryError` when
        the previous one is still running."""
        context = contextvars.copy_context()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise SpeechSummaryError(
                    "an earlier model resolution is still running, so this "
                    "reply is read whole instead of summarized"
                )
            self._thread = threading.Thread(
                target=context.run, args=(target,), daemon=True
            )
            self._thread.start()


async def _run(text: str, model: "str | Model | None", slot: ResolutionSlot) -> str:
    # Building the agent resolves the model, which may block on credentials or a
    # provider; off the loop, so the timeout still reaches it.
    agent = await _create_agent_in_daemon_thread(model, slot)
    result = await agent.run(text)
    return str(result.output or "")


async def _create_agent_in_daemon_thread(
    model: "str | Model | None", slot: ResolutionSlot
) -> "Agent[None, str]":
    """`create_speech_summarizer_agent` on *slot*'s daemon thread. A call that
    never returns is abandoned when the awaiting task is cancelled, and holds
    up neither the event loop's shutdown nor the process's exit, as an executor
    thread would; an agent it returns after that is dropped."""
    loop = asyncio.get_running_loop()
    future: "asyncio.Future[Agent[None, str]]" = loop.create_future()

    def settle(agent: "Agent[None, str] | None", error: SpeechSummaryError | None):
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        elif agent is not None:
            future.set_result(agent)

    def create() -> "Agent[None, str]":
        try:
            return create_speech_summarizer_agent(model)
        except Exception as exc:
            raise SpeechSummaryError(str(exc) or type(exc).__name__) from exc

    def work() -> None:
        agent, error = None, None
        try:
            agent = create()
        except SpeechSummaryError as exc:
            error = exc
        try:
            loop.call_soon_threadsafe(settle, agent, error)
        except RuntimeError:
            pass  # the loop closed first: nobody is waiting

    slot.start(work)
    return await future


async def summarize_for_speech(
    text: str,
    model: "str | Model | None" = None,
    timeout: float = 0,
    slot: ResolutionSlot | None = None,
) -> str:
    """A spoken summary of *text*, shorter than it. Raises `SpeechSummaryError`
    when the model fails, takes longer than *timeout* seconds (0: no limit), or
    gives back nothing or something no shorter, so the caller can read *text*
    whole. A *slot* shared between calls keeps at most one blocked model
    resolution alive; without one, each call has its own."""
    try:
        output = await asyncio.wait_for(
            _run(text, model, slot or ResolutionSlot()), timeout or None
        )
    except Exception as exc:
        raise SpeechSummaryError(str(exc) or type(exc).__name__) from exc
    summary = clean_for_speech(output)
    if not summary or len(summary) >= len(text):
        raise SpeechSummaryError(
            "the model returned a summary that is empty or no shorter than the reply"
        )
    return summary
