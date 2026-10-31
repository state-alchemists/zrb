"""Callbacks shared by the Pipecat speech and dictation pipelines."""

from __future__ import annotations

import asyncio
from collections.abc import Callable


def create_worker_stopped_handler(
    record_stopped: Callable[[str], None],
) -> Callable[[asyncio.Task[None]], None]:
    """Return a done-callback that records why the worker ended.

    Reading the exception here also prevents an unretrieved-task warning. The
    reason names the worker so a waiting segment can fail immediately instead
    of sitting until its timeout.
    """

    def on_worker_stopped(task: asyncio.Task[None]) -> None:
        reason = "the Pipecat worker stopped"
        if not task.cancelled() and task.exception() is not None:
            reason = f"{reason}: {task.exception()}"
        record_stopped(reason)

    return on_worker_stopped
