"""Delivering a message into a run that is already executing.

A queued message is normally handed to the running turn at the message loop's
next checkpoint (ADR-0078). A human who wants it in now — `Ctrl+G`, or a
message typed for a live sub-agent — reaches the run's own `enqueue` instead,
and this is the one place that decides whether the injection landed or the
caller has to queue normally.

It asks nothing of a UI: a run context is any object with `enqueue`, so the
presentation layer and the sub-agent registry both reach it from here instead
of one of them lending the other its queue.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.engine.agent.types import UserContent


def steer_into_live_run(
    run_context: Any, text: str, attachments: "Sequence[UserContent]"
) -> bool:
    """Try to inject `text`/`attachments` into the turn `run_context` belongs to.

    Returns False when there is no live run or the enqueue failed (the run
    just finished); the caller then queues normally.
    """
    if run_context is None:
        return False
    try:
        run_context.enqueue(text, *attachments, priority="asap")
        return True
    except Exception:
        CFG.LOGGER.debug(
            "steer_into_live_run: enqueue failed, falling back to queue",
            exc_info=True,
        )
        return False
