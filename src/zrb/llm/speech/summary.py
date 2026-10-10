"""Shortening a long reply for the ear: the small model's summary is spoken
instead of the reply, which stays on screen in full.

`SpeechSummarizer` makes the summary on a worker thread and guarantees the
listener hears the reply exactly once: the summary if it arrives in time, the
reply whole if the model fails, is slow, or is simply stuck. The deadline is
kept by a timer outside the worker, so the fallback never depends on the worker
returning.

A call into the model cannot always be cancelled (a blocking resolver, a
provider that ignores cancellation). Such a worker is abandoned, and its late
result dropped. A summarizer runs one worker at a time and reads later replies
whole while that one is alive, so the ceiling is one stuck thread per session,
until it returns or the process exits.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.speech.text import clean_for_speech

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


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
    gives back nothing or something no shorter. The timeout cancels the request
    only at an ``await``: it cannot interrupt a resolver that blocks while the
    agent is created, which is why the session goes through `SpeechSummarizer`,
    whose deadline is kept outside the worker."""
    try:
        output = await asyncio.wait_for(_run(text, model), timeout or None)
    except Exception as exc:
        raise SpeechSummaryError(str(exc) or type(exc).__name__) from exc
    summary = clean_for_speech(output)
    if not summary or len(summary) >= len(text):
        raise SpeechSummaryError(
            "the model returned a summary that is empty or no shorter than the reply"
        )
    return summary


async def _run(text: str, model: "str | Model | None") -> str:
    agent = create_speech_summarizer_agent(model)
    result = await agent.run(text)
    return str(result.output or "")


class SpeechSummarizer:
    """Summarizes replies for one session, one at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def start(
        self,
        text: str,
        model: "str | Model | None",
        timeout: float,
        speak: Callable[[str], None],
    ) -> None:
        """Call *speak* once, from another thread, with the summary of *text*,
        or with *text* itself when the summary fails or is not ready within
        *timeout* seconds (0: no deadline). While the previous worker is still
        running, *text* is spoken at once and no worker is started."""
        context = contextvars.copy_context()
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                logger.warning("Reading the reply whole: a summary is still stuck.")
                speak(text)
                return
            settle = _Settlement(speak)
            worker = threading.Thread(
                target=context.run,
                args=(self._work, text, model, timeout, settle),
                daemon=True,
            )
            self._worker = worker
            if timeout > 0:
                timer = threading.Timer(timeout, settle, args=(text,))
                timer.daemon = True
                settle.on_settled(timer.cancel)
                timer.start()
            worker.start()

    def _work(
        self,
        text: str,
        model: "str | Model | None",
        timeout: float,
        settle: "_Settlement",
    ) -> None:
        try:
            settle(asyncio.run(summarize_for_speech(text, model, timeout)))
        except SpeechSummaryError as exc:
            logger.warning(f"Reading the reply whole, not summarized: {exc}")
            settle(text)


class _Settlement:
    """What is spoken, decided once: the first of the worker's summary, the
    worker's failure and the deadline wins, and the rest are dropped."""

    def __init__(self, speak: Callable[[str], None]) -> None:
        self._speak = speak
        self._lock = threading.Lock()
        self._is_settled = False
        self._on_settled: list[Callable[[], None]] = []

    def on_settled(self, callback: Callable[[], None]) -> None:
        self._on_settled.append(callback)

    def __call__(self, spoken: str) -> None:
        with self._lock:
            if self._is_settled:
                return
            self._is_settled = True
        for callback in self._on_settled:
            callback()
        self._speak(spoken)
