"""Speaking a reply a sentence at a time, while the model writes it.

`StreamedReply` reads the run's stream events (it is fed by a stream
observer, `zrb.llm.stream_observer`), keeps what the reply means for the ear
(`SpokenSplitter`: a `<spoken>` block, or the whole reply when it opens none),
cuts that into sentences with `SpeechChunker` and says each one as soon as it
is complete. Text written before a tool call is spoken when the call starts, so
"Let me run the tests." is heard before the tests run.

A reply's own prose waits one sentence before it is said: a `<spoken>` block
may still follow it, and a sentence already in the ear cannot be taken back.
The wait is on the way into the chunker, not on the way out — once prose has
been cut into a sentence, the block that follows reads as the rest of it.

Events are read by their ``event_kind``/``part_kind`` tags rather than their
classes, so speech never imports pydantic-ai.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from typing import Any

from zrb.llm.speech.chunker import SpeechChunker
from zrb.llm.util.spoken import SpokenSplitter

# Where a sentence ends, as the chunker cuts: punctuation followed by space, or
# a blank line. Only the count matters here.
_SENTENCE_END_RE = re.compile(r"(?<!\.[a-zA-Z])[.!?](?=\s)|\n[ \t]*\n")


class StreamedReply:
    """The part of one turn's reply already spoken, and what is left to cut.

    Every sentence of what the reply says aloud is spoken. A reply that opens
    no `<spoken>` block says all of itself, so a model that forgets the block is
    read exactly as before it existed; a session that summarizes long replies
    does not stream them (`SpeechSession`).

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
        self._has_spoken = False
        self._is_muted = False
        self._was_muted = False
        # The reply's own prose, held until it is known whether a `<spoken>`
        # block is coming. Waiting for the *second* sentence is what makes the
        # wait worth anything: a single sentence ending does not settle it,
        # because the block the prompt asks for comes in front of the detail.
        self._pending = ""
        self._has_decided = False

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
            if _is_response_start(event):
                # A new response is a new message: a block the last one left
                # open ran to its end, not into this one.
                self._spoken.reset()
            self._speak(self._read(event))

    def mute_response(self) -> None:
        """Say nothing more of the response being written, for a user who
        talked over it; the model's next response is spoken again. What the
        user said reaches the run as a steer, so the run keeps going."""
        with self._lock:
            self._chunker.reset()
            self._spoken.reset()
            self._pending = ""
            self._has_decided = False
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
        self._spoken.reset()
        self._has_spoken = False
        self._pending = ""
        self._has_decided = False
        self._is_muted = self._was_muted = False

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
        or the reply's own while it keeps no block.

        The reply's own words wait here until the question is settled — a block
        has opened, or a second sentence has ended without one. They wait on the
        way into the chunker rather than out of it: once prose has been cut into
        a sentence, the block that follows it reads as more of the same one, and
        a sentence already said cannot be taken back.
        """
        spoken = self._spoken.feed(text)[1]
        if self._spoken.has_block:
            # A block opened: what was written in front of it was for the eye.
            self._pending = ""
            return spoken
        if self._has_decided:
            return spoken
        self._pending += spoken
        if _sentence_ends(self._pending) < 2:
            return ""
        self._has_decided = True
        released, self._pending = self._pending, ""
        return released

    def _flush(self) -> list[str]:
        """Every sentence still held: the text, or the reply, ends here."""
        said_so_far = self._spoken.flush()[1]
        if not self._spoken.has_block:
            # The reply opened no block, or the one it opened came too late to
            # claim the prose: the question is settled, so the prose is said.
            said_so_far = self._pending + said_so_far
        self._pending = ""
        chunks = self._chunker.feed(said_so_far) if said_so_far else []
        return chunks + self._chunker.flush()

    def _speak(self, chunks: list[str]) -> None:
        for chunk in chunks:
            self._say(chunk)
            self._has_spoken = True


def _sentence_ends(text: str) -> int:
    """How many sentences end in *text*, by the chunker's own rule."""
    return len(_SENTENCE_END_RE.findall(text))


def _is_response_start(event: Any) -> bool:
    """Whether *event* opens a new model response: its first part."""
    return (
        getattr(event, "event_kind", None) == "part_start"
        and getattr(event, "index", None) == 0
    )
