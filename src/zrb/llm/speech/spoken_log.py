"""What zrb said aloud lately, and when.

On speakers, with barge-in on, the microphone hears zrb's own voice. Now
and then it is loud enough to get past the bar over it, and is transcribed
into zrb's own words, which would reach the model as a turn — zrb talking to
itself. Dictation reads this log to drop a transcript that only repeats what
zrb was saying when it was heard.

One process-wide instance, `spoken_log`: the speakers and the microphone are
one room. Times are `time.monotonic()`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

_SECONDS_KEPT = 120.0


@dataclass
class SpokenEntry:
    """One sentence zrb said, from *started_at* to *ended_at* (``None``
    while it is still being said)."""

    text: str
    started_at: float
    ended_at: float | None = None


class SpokenLog:
    """The sentences zrb said in the last *seconds*."""

    def __init__(self, seconds: float = _SECONDS_KEPT) -> None:
        self._seconds = seconds
        self._entries: list[SpokenEntry] = []
        self._lock = threading.Lock()

    def start(self, text: str, at: float) -> SpokenEntry:
        """Record *text* starting to be said at *at*; `finish` the entry
        returned once it has been said."""
        entry = SpokenEntry(text, at)
        with self._lock:
            self._entries = [
                kept
                for kept in self._entries
                if kept.ended_at is None or kept.ended_at >= at - self._seconds
            ]
            self._entries.append(entry)
        return entry

    def finish(self, entry: SpokenEntry, at: float) -> None:
        with self._lock:
            entry.ended_at = at

    def get_text_said(self, start: float, end: float, tail: float = 0.0) -> str:
        """What zrb said between *start* and *end*, counting each sentence
        as heard for *tail* seconds after it ended (the room's echo)."""
        with self._lock:
            return " ".join(
                entry.text
                for entry in self._entries
                if entry.started_at <= end
                and (entry.ended_at is None or entry.ended_at + tail >= start)
            )


spoken_log = SpokenLog()
