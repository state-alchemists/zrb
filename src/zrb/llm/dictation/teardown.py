"""Closing a resource that is already on its way out.

Used for a microphone stream that would not start, a transcription stream given
up on, and the Pipecat pipeline the capture is pushed into (ADR-0107). None has
anyone left to report its failure to, and a failure must not reach the listening
around it, so closing is best-effort.
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

    *close* may be sync (a `sounddevice` stream) or async (a transcription
    stream, a Pipecat worker's cancel). Cancellation still propagates.
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

    Returns the tasks that finished. A task that swallows its cancellation
    cannot be forced, so one still going at the deadline is logged and left
    rather than holding up the teardown. Its exception is read off whenever it
    does end, so the loop does not report it as never retrieved.
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
