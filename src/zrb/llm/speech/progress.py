"""Saying what zrb is doing while a tool runs, so a long turn is not silent.

`ProgressNarrator` watches the run's stream (through a stream observer) and,
when a tool call starts after a stretch in which nothing was said, speaks a
short template line: "Running a command." A template, not a model call, as
for approvals: the moment has passed by the time a model answers.

A line still queued when its tool finishes is dropped, and nothing is said
while the model's own words are being spoken, so the narration only fills
silence.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from zrb.config.config import CFG
from zrb.llm.speech.player import IsStale
from zrb.llm.speech.text import match_tool_phrase


def describe_tool_progress(
    tool: str | None, phrases: dict[str, str] | None = None
) -> str | None:
    """A spoken line saying what a tool call is doing, from *phrases*
    (default: `CFG.LLM_SPEECH_PROGRESS_PHRASES`); ``None`` for a tool no
    pattern matches, which is not announced."""
    if phrases is None:
        phrases = CFG.LLM_SPEECH_PROGRESS_PHRASES
    return match_tool_phrase(tool, phrases)


class ProgressNarrator:
    """Speaks a tool call's progress line when nothing was said for
    *interval* seconds (``0``: never), except for *silent_tools*, in the
    words of *phrases* (defaults: `CFG.LLM_SPEECH_PROGRESS_SILENT_TOOLS`,
    `CFG.LLM_SPEECH_PROGRESS_PHRASES`).

    *say* queues a line with a staleness check; *seconds_since_said* is how
    long since anything was last queued, by this or anything else speaking
    for the session.
    """

    def __init__(
        self,
        say: Callable[[str, IsStale], None],
        seconds_since_said: Callable[[], float],
        interval: float,
        silent_tools: list[str] | None = None,
        phrases: dict[str, str] | None = None,
    ) -> None:
        self._phrases = phrases
        if silent_tools is None:
            silent_tools = CFG.LLM_SPEECH_PROGRESS_SILENT_TOOLS
        self._silent_tools = set(silent_tools)
        self._say = say
        self._seconds_since_said = seconds_since_said
        self._interval = max(interval, 0.0)
        self._lock = threading.Lock()
        # The current turn's live calls, by call id: the generation each was
        # announced in.
        self._running: dict[str, int] = {}
        # Calls a stopped turn left running, by call id: their result is still
        # to come, and it has to settle one of these rather than drop a live call
        # a later turn started under the same id.
        self._unsettled: dict[str, int] = {}
        # Bumped by `reset`. Every queued line carries the generation it was
        # queued in, so a line from an earlier turn stays stale even after the
        # same tool-call id is used again, and one still being decided on when
        # the turn stops is never queued at all.
        self._generation = 0

    def handle_event(self, event: Any) -> None:
        kind = getattr(event, "event_kind", None)
        if kind == "function_tool_call":
            # Read before deciding: the whole decision below belongs to this
            # turn, so a stop landing part-way through must invalidate it.
            with self._lock:
                generation = self._generation
            self._start(getattr(event, "part", None), generation)
        elif kind == "function_tool_result":
            self._finish(_result_call_id(event))

    def _finish(self, call_id: str) -> None:
        """Book a tool result.

        A result names only its call id, and it can arrive after that id has
        been reused by a later turn. The call a stopped turn left running is
        settled first, so a late result cannot drop the call the current turn
        started under the same id.
        """
        with self._lock:
            owed = self._unsettled.get(call_id, 0)
            if owed:
                if owed == 1:
                    del self._unsettled[call_id]
                else:
                    self._unsettled[call_id] = owed - 1
                return
            self._running.pop(call_id, None)

    def _start(self, part: Any, generation: int) -> None:
        tool = getattr(part, "tool_name", None)
        call_id = str(getattr(part, "tool_call_id", "") or "")
        if not self._interval or tool in self._silent_tools:
            return
        if self._seconds_since_said() < self._interval:
            return
        line = describe_tool_progress(tool, self._phrases)
        if not line:
            return
        with self._lock:
            if generation != self._generation:
                # The turn stopped while this line was being decided on: it
                # would be spoken after the turn, so it is not queued.
                return
            self._running[call_id] = generation
        self._say(line, lambda: self._is_finished(call_id, generation))

    def _is_finished(self, call_id: str, generation: int) -> bool:
        """Whether the line queued for *call_id* in *generation* is stale: its
        tool call has ended, or its turn has."""
        with self._lock:
            if generation != self._generation:
                return True
            return self._running.get(call_id) != generation

    def reset(self) -> None:
        """Drop progress lines still queued when the turn ends.

        A call still running becomes a result the narrator has to expect, so
        that when it arrives it settles this turn instead of a later turn's
        call of the same id."""
        with self._lock:
            self._generation += 1
            for call_id in self._running:
                self._unsettled[call_id] = self._unsettled.get(call_id, 0) + 1
            self._running.clear()


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
