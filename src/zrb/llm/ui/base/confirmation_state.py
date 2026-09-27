"""Pending tool-call/ask-user confirmation state for `BaseUI`.

Self-contained like `BaseUIUsage`: the actual queueing/resolution logic lives
in `UIConfirmation` (`llm/ui/default/confirmation.py`), which reaches this
state through `BaseUI.confirmation` — so this part, like that one, needs no
reference back to the owner.
"""

from __future__ import annotations

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
        # Buffer for main-agent output during confirmation (avoids interleaving).
        self.output_buffer: list[str] = []

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

    @property
    def current_spec(self) -> Any:
        """`current`'s `ChoiceSpec`, or ``None`` for a plain-text request."""
        current = self._current
        return next((entry[2] for entry in self.queue if entry[0] is current), None)
