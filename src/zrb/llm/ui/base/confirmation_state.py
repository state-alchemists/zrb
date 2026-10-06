"""Pending tool-call/ask-user confirmation state for `BaseUI`; the logic is
in `UIConfirmation` (`llm/ui/default/confirmation.py`)."""

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
        # (time asked, future) per request, oldest first. A finished entry
        # followed by a finished one is pruned: lookups land on the next,
        # equally finished. Read from other threads.
        self._asked: "list[tuple[float, asyncio.Future[str]]]" = []
        self._asked_lock = threading.Lock()
        # Main-agent output held while a confirmation is pending, as
        # unstyled (text, kind) pairs replayed through `append_to_output`.
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
        """Whether the first request asked at or after *asked_at* is done.

        Thread-safe.
        """
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
