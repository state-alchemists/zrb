"""Closing a resource that is already on its way out.

Three teardowns share this: a microphone stream that would not start, an
utterance's transcription stream given up on instead of finished, and the Pipecat
pipeline the capture was pushed into (ADR-0106, stage 1) — inside which the worker
driving it is asked to stop. None of them has anyone left to report its own
failure to, and a failure in any of them must not reach the listening going on
around it. The call is best-effort, here in one place rather than as a copy of the
same `try` in each module that closes something.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


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
