"""Saying what zrb is doing while a tool runs, so a long turn is not silent.

`ProgressNarrator` watches the run's stream (through a stream observer) and,
when a tool call starts after a stretch in which nothing was said, speaks a
short template line: "Running a command." A template, not a model call, as
for approvals (ADR-0103): the moment has passed by the time a model answers.

A line still queued when its tool finishes is dropped, and nothing is said
while the model's own words are being spoken, so the narration only fills
silence.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from zrb.llm.speech.player import IsStale

_TOOL_PROGRESS = {
    "Read": "Reading a file.",
    "AnalyzeFile": "Reading a file.",
    "LS": "Looking through the files.",
    "Glob": "Looking through the files.",
    "Grep": "Searching the code.",
    "AnalyzeCode": "Reading the code.",
    "Write": "Writing a file.",
    "Edit": "Editing a file.",
    "MV": "Moving a file.",
    "RM": "Removing a file.",
    "Shell": "Running a command.",
    "Bash": "Running a command.",
    "WebSearch": "Searching the web.",
    "WebFetch": "Reading a web page.",
    "DelegateToAgent": "Handing this to a sub-agent.",
    "DelegateToAgentBackground": "Handing this to a sub-agent.",
}
# Bookkeeping tools that are over too fast to be worth a word.
_SILENT_TOOLS = {"TodoRead", "TodoWrite", "ActivateSkill", "SearchSkill"}


def describe_tool_progress(tool: str | None) -> str:
    """A spoken line saying what a tool call is doing."""
    if tool in _TOOL_PROGRESS:
        return _TOOL_PROGRESS[tool]
    if tool and tool.startswith("Lsp"):
        return "Checking the code."
    return f"Using the {tool} tool." if tool else "Working on it."


class ProgressNarrator:
    """Speaks a tool call's progress line when nothing was said for
    *interval* seconds (``0``: never).

    *say* queues a line with a staleness check; *seconds_since_said* is how
    long since anything was last queued, by this or anything else speaking
    for the session.
    """

    def __init__(
        self,
        say: Callable[[str, IsStale], None],
        seconds_since_said: Callable[[], float],
        interval: float,
    ) -> None:
        self._say = say
        self._seconds_since_said = seconds_since_said
        self._interval = max(interval, 0.0)
        self._lock = threading.Lock()
        self._running: set[str] = set()

    def handle_event(self, event: Any) -> None:
        kind = getattr(event, "event_kind", None)
        if kind == "function_tool_call":
            self._start(getattr(event, "part", None))
        elif kind == "function_tool_result":
            with self._lock:
                self._running.discard(_result_call_id(event))

    def _start(self, part: Any) -> None:
        tool = getattr(part, "tool_name", None)
        call_id = str(getattr(part, "tool_call_id", "") or "")
        if not self._interval or tool in _SILENT_TOOLS:
            return
        if self._seconds_since_said() < self._interval:
            return
        with self._lock:
            self._running.add(call_id)
        self._say(describe_tool_progress(tool), lambda: self._is_finished(call_id))

    def _is_finished(self, call_id: str) -> bool:
        with self._lock:
            return call_id not in self._running


def _result_call_id(event: Any) -> str:
    call_id = getattr(event, "tool_call_id", None)
    if call_id is None:
        call_id = getattr(getattr(event, "result", None), "tool_call_id", "")
    return str(call_id or "")


class SpeechClock:
    """When a session last queued something to say."""

    def __init__(self) -> None:
        self._said_at = float("-inf")

    def mark(self) -> None:
        self._said_at = time.monotonic()

    def seconds_since_said(self) -> float:
        return time.monotonic() - self._said_at
