"""Speaking a reply a sentence at a time, while the model writes it.

`StreamedReply` reads the run's stream events (it is fed by a stream
observer, `zrb.llm.shared.stream_observer`), keeps what the reply means for the ear
(`SpokenSplitter`: a `<spoken>` block, or the whole reply when it opens none),
cuts that into sentences with `SpeechChunker` and says each one as soon as it
is complete. Text written before a tool call is spoken when the call starts, so
"Let me run the tests." is heard before the tests run.

Only a `<spoken>` block is said while the reply streams. The prose around it
is for the eye, and none of it is said on the chance that no block follows:
a response that opens no block is read whole when the turn ends, by the stop
hook.

Events are read by their ``event_kind``/``part_kind`` tags rather than their
classes, so speech never imports pydantic-ai.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from zrb.llm.speech.chunker import SpeechChunker
from zrb.llm.util.spoken import SpokenSplitter


class StreamedReply:
    """The part of one turn's last response already spoken, and what is left.

    Every sentence of a `<spoken>` block is said as it completes. A response
    with no block claims nothing here and is read whole when the turn ends; a
    claim made by an earlier response in the same turn is not carried into this
    one (`_reset_spoken`), so a block that spoke first does not silence the
    answer written after it. A session that summarizes long replies does not
    stream them (`SpeechSession`).

    *max_chars*, when given, is the longest run of prose said as one piece:
    the speech backend's own limit, which the chunker cannot know. Events
    arrive on the event loop and the turn ends on a hook thread, so every
    method holds a lock.
    """

    def __init__(
        self, say: Callable[[str], None], max_chars: int | None = None
    ) -> None:
        self._say = say
        self._lock = threading.Lock()
        self._chunker = (
            SpeechChunker() if max_chars is None else SpeechChunker(max_chars=max_chars)
        )
        self._spoken = SpokenSplitter()
        # Blocks only: a stream cannot take back a sentence once it is in the
        # ear, so the prose around a block is never guessed at. A reply with no
        # block claims nothing (`has_claimed_turn` stays false) and the stop
        # hook speaks it whole.
        self._spoken.speak_only_blocks()
        self._has_spoken = False
        self._is_muted = False
        self._was_muted = False

    @property
    def has_claimed_turn(self) -> bool:
        """Whether the last response is streaming's to speak: some of it was
        spoken, or the user talked over it. Either way, that message must not be
        spoken again when the turn ends — while a response that said nothing,
        and whose prose no block marked, is still the turn's last word and the
        stop hook's to read whole."""
        return self._has_spoken or self._was_muted

    def handle_event(self, event: Any) -> None:
        """Speak whatever sentences *event* completes."""
        with self._lock:
            if self._is_muted and not _is_response_start(event):
                return
            self._is_muted = False
            if _is_response_start(event):
                # A new response is a new message: a block the last one left
                # open ran to its end, not into this one.
                self._reset_spoken()
                # And nobody has talked over it: a hush that arrived before it
                # started — a new message submitted between turns, which is what
                # `interrupt_speech` does — muted a response that was already
                # over, and must not go on claiming this one. `_was_muted` is
                # for the response the user actually talked over, and that one
                # has already started (its `part_start` came before the hush).
                self._was_muted = False
            self._speak(self._read(event))

    def mute_response(self) -> None:
        """Say nothing more of the response being written, for a user who
        talked over it; the model's next response is spoken again. What the
        user said reaches the run as a steer, so the run keeps going.

        The claim this makes is on the response being written: one that starts
        after it is spoken as usual (`handle_event`)."""
        with self._lock:
            self._chunker.reset()
            self._reset_spoken()
            self._is_muted = self._was_muted = True

    def flush(self) -> None:
        """Speak what is left of the turn, however short; it has ended."""
        with self._lock:
            if not self._is_muted:
                self._speak(self._flush())

    def reset(self) -> None:
        """Drop the turn without speaking the rest of it."""
        with self._lock:
            self._reset()

    def _reset(self) -> None:
        self._chunker.reset()
        self._reset_spoken()
        self._is_muted = self._was_muted = False

    def _reset_spoken(self) -> None:
        """A fresh message: a new splitter, still blocks-only, and no claim yet.

        The claim is the *response's*, not the turn's. A block said in an earlier
        response has already been heard and says nothing about this one, so
        leaving `_has_spoken` set would mark the turn spoken from its first
        block and lose the last response's unmarked prose — the answer to the
        turn — because the stop hook reads only an unclaimed response. `reset`
        puts `_speaks_outside` back on, and this stream must not have it."""
        self._spoken.reset()
        self._spoken.speak_only_blocks()
        self._has_spoken = False

    def _read(self, event: Any) -> list[str]:
        kind = getattr(event, "event_kind", None)
        if kind == "part_start":
            part_kind = getattr(event.part, "part_kind", None)
            if part_kind == "text":
                return self._chunker.feed(
                    self._sayable(getattr(event.part, "content", "") or "")
                )
            if part_kind in ("tool-call", "builtin-tool-call"):
                return self._flush()
            return []
        if kind == "part_delta":
            delta = event.delta
            if getattr(delta, "part_delta_kind", None) == "text":
                return self._chunker.feed(
                    self._sayable(getattr(delta, "content_delta", "") or "")
                )
            return []
        if kind == "part_end" and getattr(event.part, "part_kind", None) == "text":
            return self._flush()
        if kind in ("function_tool_call", "agent_run_result"):
            return self._flush()
        return []

    def _sayable(self, text: str) -> str:
        """What of *text* is meant for the ear: a `<spoken>` block's own words,
        and nothing at all while the reply is outside one."""
        return self._spoken.feed(text)[1]

    def _flush(self) -> list[str]:
        """Every sentence still held: the text, or the reply, ends here."""
        said_so_far = self._spoken.flush()[1]
        chunks = self._chunker.feed(said_so_far) if said_so_far else []
        return chunks + self._chunker.flush()

    def _speak(self, chunks: list[str]) -> None:
        for chunk in chunks:
            self._say(chunk)
            self._has_spoken = True


def _is_response_start(event: Any) -> bool:
    """Whether *event* opens a new model response: its first part."""
    return (
        getattr(event, "event_kind", None) == "part_start"
        and getattr(event, "index", None) == 0
    )
