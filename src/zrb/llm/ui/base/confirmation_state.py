"""Pending tool-call/ask-user confirmation state for `BaseUI`.

Self-contained like `BaseUIUsage`: the actual queueing/resolution logic lives
in `UIConfirmation` (`llm/ui/default/confirmation.py`), which reaches this
state through `BaseUI.confirmation` — so this part, like that one, needs no
reference back to the owner.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio


class BaseUIConfirmationState:
    """The pending-confirmation queue, its active entry, and the output
    buffer held while a confirmation is on screen."""

    def __init__(self) -> None:
        # Each queue entry is (future, prompt, spec, agent_id); spec is a
        # ChoiceSpec for AskUserQuestion-style requests, else None for plain
        # text; agent_id is the originating sub-agent's id, or None for the
        # main agent.
        self.queue: "list[tuple[asyncio.Future[str], str, Any, str | None]]" = []
        self._current: "asyncio.Future[str] | None" = None
        self._timed: "asyncio.Future[str] | None" = None
        self._current_since = 0.0
        # (time asked, future) per request, oldest first. A finished request
        # followed by a finished one is dropped: a lookup that would have
        # found it finds the next one, just as finished. What is left is at
        # most two entries per unfinished request, plus the newest. Read from
        # other threads.
        self._asked: "list[tuple[float, asyncio.Future[str]]]" = []
        self._asked_lock = threading.Lock()
        # Main-agent output held during confirmation (avoids interleaving):
        # each chunk's final text and its `append_to_output` kind, unstyled,
        # so it replays exactly as it would have been appended.
        self.output_buffer: list[tuple[str, str]] = []

    @property
    def current(self) -> "asyncio.Future[str] | None":
        """The request on screen, which the next answer resolves."""
        return self._current

    @current.setter
    def current(self, future: "asyncio.Future[str] | None") -> None:
        self._current = future
        # Timed by identity: flushing buffered output clears and restores the
        # same request, which must keep the time it first appeared.
        if future is not None and future is not self._timed:
            self._timed = future
            self._current_since = time.monotonic()

    @property
    def current_since(self) -> float | None:
        """`time.monotonic()` when `current` appeared, ``None`` without one."""
        return self._current_since if self._current is not None else None

    def handle_asked(self, future: "asyncio.Future[str]") -> None:
        """Date a new request, which ends when *future* is done."""
        with self._asked_lock:
            asked = self._asked
            asked.append((time.monotonic(), future))
            self._asked = [
                entry
                for entry, following in zip(asked, asked[1:])
                if not (entry[1].done() and following[1].done())
            ] + [asked[-1]]

    def is_answered_since(self, asked_at: float) -> bool:
        """Whether the first request asked at or after *asked_at* has been
        answered or cancelled, in whatever order the requests were answered.
        Safe to call from another thread."""
        with self._asked_lock:
            for since, future in self._asked:
                if since >= asked_at:
                    return future.done()
        return False

    @property
    def current_spec(self) -> Any:
        """`current`'s `ChoiceSpec`, or ``None`` for a plain-text request."""
        current = self._current
        return next((entry[2] for entry in self.queue if entry[0] is current), None)
