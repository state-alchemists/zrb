"""Speaking a reply a sentence at a time, while the model writes it.

`StreamedReply` reads the run's stream events (it is fed by a stream
observer, `zrb.llm.stream_observer`), cuts the text into sentences with
`SpeechChunker` and says each one as soon as it is complete. Text written
before a tool call is spoken when the call starts, so "Let me run the tests."
is heard before the tests run.

Events are read by their ``event_kind``/``part_kind`` tags rather than their
classes, so speech never imports pydantic-ai.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from zrb.llm.speech.chunker import SpeechChunker


class StreamedReply:
    """The part of one turn's reply already spoken, and what is left to cut.

    *max_chars* caps what one turn speaks (``0``: no cap): the sentence that
    crosses it is spoken whole, then *note* once, then nothing more that turn.
    Events arrive on the event loop and the turn ends on a hook thread, so
    every method holds a lock.
    """

    def __init__(self, say: Callable[[str], None], max_chars: int, note: str) -> None:
        self._say = say
        self._max_chars = max(max_chars, 0)
        self._note = note
        self._lock = threading.Lock()
        self._chunker = SpeechChunker()
        self._spoken_chars = 0
        self._has_spoken = False
        self._is_noted = False
        self._is_muted = False
        self._was_muted = False

    @property
    def has_claimed_turn(self) -> bool:
        """Whether this turn's reply is streaming's to speak: some of it was
        spoken, or the user talked over it. Either way, the whole reply must
        not be spoken again when the turn ends."""
        return self._has_spoken or self._was_muted

    def handle_event(self, event: Any) -> None:
        """Speak whatever sentences *event* completes."""
        with self._lock:
            if self._is_muted and not _is_response_start(event):
                return
            self._is_muted = False
            self._speak(self._read(event))

    def mute_response(self) -> None:
        """Say nothing more of the response being written, for a user who
        talked over it; the model's next response is spoken again. What the
        user said reaches the run as a steer, so the run keeps going."""
        with self._lock:
            self._chunker.reset()
            self._is_muted = self._was_muted = True

    def flush(self) -> None:
        """Speak what is left of the turn, however short; it has ended."""
        with self._lock:
            if not self._is_muted:
                self._speak(self._chunker.flush())

    def reset(self) -> None:
        """Drop the turn without speaking the rest of it."""
        with self._lock:
            self._reset()

    def _reset(self) -> None:
        self._chunker.reset()
        self._spoken_chars = 0
        self._has_spoken = self._is_noted = False
        self._is_muted = self._was_muted = False

    def _read(self, event: Any) -> list[str]:
        kind = getattr(event, "event_kind", None)
        if kind == "part_start":
            part_kind = getattr(event.part, "part_kind", None)
            if part_kind == "text":
                return self._chunker.feed(getattr(event.part, "content", "") or "")
            if part_kind in ("tool-call", "builtin-tool-call"):
                return self._chunker.flush()
            return []
        if kind == "part_delta":
            delta = event.delta
            if getattr(delta, "part_delta_kind", None) == "text":
                return self._chunker.feed(getattr(delta, "content_delta", "") or "")
            return []
        if kind == "part_end" and getattr(event.part, "part_kind", None) == "text":
            return self._chunker.flush()
        if kind in ("function_tool_call", "agent_run_result"):
            return self._chunker.flush()
        return []

    def _speak(self, chunks: list[str]) -> None:
        for chunk in chunks:
            if self._max_chars and self._spoken_chars >= self._max_chars:
                if not self._is_noted and self._note:
                    self._say(self._note)
                self._is_noted = True
                return
            self._say(chunk)
            self._spoken_chars += len(chunk)
            self._has_spoken = True


def _is_response_start(event: Any) -> bool:
    """Whether *event* opens a new model response: its first part."""
    return (
        getattr(event, "event_kind", None) == "part_start"
        and getattr(event, "index", None) == 0
    )
