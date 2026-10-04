"""Closing a resource that is already on its way out.

Three teardowns share this: a microphone stream that would not start, an
utterance's transcription stream given up on instead of finished, and the Pipecat
pipeline the capture was pushed into (ADR-0107, stage 1) — inside which the worker
driving it is asked to stop. None of them has anyone left to report its own
failure to, and a failure in any of them must not reach the listening going on
around it. The call is best-effort, here in one place rather than as a copy of the
same `try` in each module that closes something.

Two of those teardowns then wait for a task they cancelled, with a deadline. That
wait is here too, for the same reason the `try` is: how long to wait, and what to
say when the wait is over, is one decision. A task that swallows its cancellation
says the same thing wherever it is, and there is nothing else to say about it.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


async def close_quietly(close: Callable[[], object], what: str) -> None:
    """Close *what* through *close*; a failure is logged, never raised.

    *close* is called whether it is sync (a `sounddevice` stream) or async (a
    transcription stream, a Pipecat worker's cancel). Whatever is being closed is
    already on its way out, so there is no caller left for it to fail to: what
    went wrong is logged, and nothing is raised. A caller with a second way to end
    *what* takes it once this returns — `AudioPipeline.close` ends the task
    driving its pipeline when the ask it made did not land. Cancellation is not a
    failure of the close, and still propagates.
    """
    try:
        result = close()
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        logger.warning(f"Closing {what} failed: {exc}")


async def cancel_and_wait(
    task: "asyncio.Task[_T]", what: str, timeout: float
) -> "set[asyncio.Task[_T]]":
    """Cancel *task* and wait, at most *timeout*, for it to unwind.

    Returns the tasks that finished, which is what a caller reads an exception
    off. A cancellation the task swallows cannot be forced from here — only the
    work it is stuck in could end it — so a task still going when the deadline
    passes is named in the log and left behind, rather than waited on for as long
    as it likes while the teardown it is part of is held up. Its exception is read
    off whenever it does end, so the loop does not report it later as one nobody
    retrieved.
    """
    task.add_done_callback(_read_exception_off)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=timeout)
    if not done:
        logger.warning(f"{what} is still running after being cancelled")
    return done


def _read_exception_off(task: "asyncio.Task[object]") -> None:
    """Take a finished task's exception, so the loop does not report it later."""
    if not task.cancelled():
        task.exception()
