"""Watching an agent run's stream of events from outside the UI.

An observer is called with every streamed event after the UI's handler (e.g.
`enable_speech` speaks the reply a sentence at a time). Observers are on the hot
path and must return quickly; one that raises is logged and skipped.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

# Called with each `AgentStreamEvent`; may return an awaitable.
StreamObserver = Callable[[Any], Any]


def create_observed_event_handler(
    event_handler: Callable[[Any], Any] | None,
    observers: Sequence[StreamObserver] | None,
) -> Callable[[Any], Any] | None:
    """*event_handler*, also passing every event to each of *observers* after
    it. *event_handler* itself when there are no observers."""
    if not observers:
        return event_handler
    observer_list = list(observers)

    async def handle_event(event: Any) -> None:
        if event_handler is not None:
            await event_handler(event)
        for observer in observer_list:
            await _notify(observer, event)

    return handle_event


async def _notify(observer: StreamObserver, event: Any) -> None:
    try:
        result = observer(event)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        logger.warning(f"Stream observer {observer!r} failed: {exc}")
