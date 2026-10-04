"""Closing a resource the listening must outlive.

Two teardowns here can fail while the microphone is still open: an utterance's
transcription stream, given up on instead of finished, and the Pipecat pipeline
the capture was pushed into (ADR-0106, stage 1) — inside which the worker
driving it is asked to stop. Neither has anyone left to report its own failure
to, and the pipeline decides nothing, so a failure in either must not reach the
listening still going on around it. One best-effort call is what they share,
rather than copies of the same `try` in each module that closes something.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def close_quietly(close: Callable[[], Awaitable[None]], what: str) -> None:
    """Close *what* through *close*; a failure is logged, never raised.

    Whatever is being closed is already on its way out, so there is no caller
    left for it to fail to: what went wrong is logged, and nothing is raised.
    A caller with a second way to end *what* takes it once this returns —
    `AudioPipeline.close` ends the task driving its pipeline when the ask it
    made did not land. Cancellation is not a failure of the close, and still
    propagates.
    """
    try:
        await close()
    except Exception as exc:
        logger.warning(f"Closing {what} failed: {exc}")
