"""What zrb's speakers played, and when, for cancelling it out of the mic.

When zrb plays speech itself (`PcmUtterance`), each chunk is written here at
the moment it reaches the speakers, resampled to 16 kHz. Dictation reads the
same stretch of time for each microphone block and hands both to its echo
canceller, which subtracts zrb's voice from what the microphone heard.

One process-wide instance, `echo_reference`, since the speakers and the
microphone are shared by every session in the process. Timestamps are
`time.monotonic()` seconds.
"""

from __future__ import annotations

import threading
from typing import Any

RATE = 16000
_SECONDS_KEPT = 10.0


class EchoReference:
    """A ring of the last few seconds of played audio, indexed by time."""

    def __init__(self, origin: float = 0.0, seconds: float = _SECONDS_KEPT) -> None:
        self._origin = origin
        self._size = int(RATE * seconds)
        self._ring: Any = None  # numpy, created on first write
        self._written_until = 0  # sample index one past the newest write
        self._active = 0  # utterances writing here now
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        """Whether an utterance zrb plays itself is playing: the echo of
        what is playing now can be cancelled."""
        return self._active > 0

    def add_player(self, change: int) -> None:
        """Count an utterance starting (+1) or ending (-1) its playback."""
        with self._lock:
            self._active = max(0, self._active + change)

    def write(self, start_time: float, samples: Any) -> None:
        """Record 16 kHz float32 *samples* reaching the speakers from
        *start_time* on."""
        np = _numpy()
        with self._lock:
            if self._ring is None:
                self._ring = np.zeros(self._size, np.float32)
            start = self._to_index(start_time)
            # Silence between the last write and this one, not stale audio.
            gap = start - self._written_until
            if gap >= self._size:
                self._ring.fill(0)
            elif gap > 0:
                self._fill(self._written_until, np.zeros(gap, np.float32))
            self._fill(start, samples)
            self._written_until = max(self._written_until, start + len(samples))

    def read(self, start_time: float, length: int) -> Any:
        """*length* samples played from *start_time* on; silence where
        nothing was played, or it is too old to be kept."""
        np = _numpy()
        out = np.zeros(length, np.float32)
        with self._lock:
            if self._ring is None:
                return out
            indexes = np.arange(length) + self._to_index(start_time)
            kept = (indexes >= self._written_until - self._size) & (
                indexes < self._written_until
            )
            out[kept] = self._ring[indexes[kept] % self._size]
        return out

    def _to_index(self, when: float) -> int:
        return int(round((when - self._origin) * RATE))

    def _fill(self, start: int, samples: Any) -> None:
        for offset in range(0, len(samples), self._size):
            part = samples[offset : offset + self._size]
            first = (start + offset) % self._size
            head = min(len(part), self._size - first)
            self._ring[first : first + head] = part[:head]
            self._ring[: len(part) - head] = part[head:]


def _numpy() -> Any:
    # lazy: heavy third-party (numpy is a zrb[voice] extra); only reached
    # while zrb plays speech itself, which needs it anyway.
    import numpy

    return numpy


echo_reference = EchoReference()
