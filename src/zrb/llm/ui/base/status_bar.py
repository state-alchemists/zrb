"""The status bar's own state for `BaseUI`: the working period and badges."""

from __future__ import annotations

import time
from typing import NamedTuple


class RunningTool(NamedTuple):
    """A tool call currently executing; ``started_at`` is ``time.monotonic()``."""

    tool_name: str
    tool_call_id: str
    started_at: float


class BaseUIStatusBar:
    """Track what the status bar shows: the working timer, running tools, badges."""

    def __init__(self) -> None:
        self._working_started_at: float | None = None
        self._running_tools: dict[str, RunningTool] = {}
        self._badges: dict[str, str] = {}

    def start_working(self) -> None:
        """Start the working period, unless one is already running."""
        if self._working_started_at is None:
            self._working_started_at = time.monotonic()

    def stop_working(self) -> None:
        """End the working period, resetting the timer."""
        self._working_started_at = None

    @property
    def working_started_at(self) -> float | None:
        """`time.monotonic()` when the current working period began."""
        return self._working_started_at

    @property
    def running_tool(self) -> RunningTool | None:
        """The most recently started tool call still executing, or None."""
        if not self._running_tools:
            return None
        return max(self._running_tools.values(), key=lambda item: item.started_at)

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """Record the start of `tool_name`'s execution for the status bar."""
        self._running_tools[tool_call_id] = RunningTool(
            tool_name, tool_call_id, time.monotonic()
        )

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """Forget the finished call `tool_call_id`; ``None`` clears all."""
        if tool_call_id is None:
            self._running_tools.clear()
            return
        self._running_tools.pop(tool_call_id, None)

    def set_badge(self, key: str, text: str | None) -> None:
        """Show *text* under *key*; ``None`` takes that key's badge away."""
        if text is None:
            self._badges.pop(key, None)
        else:
            self._badges[key] = text

    @property
    def badges(self) -> tuple[str, ...]:
        """The badges set so far, in the order first set."""
        return tuple(self._badges.values())
