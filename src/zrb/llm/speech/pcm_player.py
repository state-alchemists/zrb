"""Playing speech in zrb's own process, through sounddevice.

A `PcmUtterance` plays `SpeechAudio` through an output stream instead of a
player program. zrb then knows every sample it plays: each is written to
`echo_reference` as it reaches the speakers, so dictation can cancel zrb's
voice out of the microphone, and playback can pause and resume, so a cough
heard over zrb only stalls it for a moment.

It needs sounddevice and numpy (the zrb[voice] extra); `is_available` says
whether they import, and speech falls back to player programs when not.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.echo_reference import (
    RATE,
    EchoReference,
    echo_reference,
    get_monotonic_time,
)

_BLOCK_FRAMES = 1024
_MAX_BUFFERED = 32
_BUFFER_POLL_SECONDS = 0.005
_available: bool | None = None


def is_available() -> bool:
    """Whether sounddevice and numpy import, so speech can play in process."""
    global _available
    if _available is None:
        try:
            _import_audio()
            _available = True
        except (ImportError, OSError):
            _available = False
    return _available


class PcmUtterance(Utterance):
    """`SpeechAudio` played through a sounddevice output stream."""

    def __init__(self, audio: SpeechAudio, reference: EchoReference | None = None):
        super().__init__([])
        self._audio = audio
        self._reference = reference or echo_reference
        self._buffer: deque[bytes] = deque()
        self._pending = b""
        self._is_source_done = False
        self._is_paused = False
        self._finished = threading.Event()
        # Every frame the stream has asked for, silence included, so a
        # sample's time stays true across pauses and download stalls.
        self._frames_elapsed = 0
        self._started_at = 0.0

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_pausable(self) -> bool:
        return True

    def pause(self) -> None:
        """Hold playback where it is; silence until `resume`."""
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def play(self, timeout: float | None) -> None:
        """Play to the end, or until *timeout* seconds or `stop`."""
        if self.is_stopped:
            return
        np, sd = _import_audio()
        reader = threading.Thread(target=self._read_source, daemon=True)
        reader.start()
        self._reference.add_player(+1)
        try:
            stream = sd.OutputStream(
                samplerate=self._audio.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=_BLOCK_FRAMES,
                callback=lambda out, frames, info, status: self._fill(
                    np, sd, out, frames, info
                ),
                finished_callback=self._finished.set,
            )
            # Before the stream starts, so its first callback sees it; only
            # used when the host gives no timestamps.
            self._started_at = time.monotonic() + float(stream.latency)
            with stream:
                if not self._finished.wait(timeout):
                    self.stop()
        finally:
            self._reference.add_player(-1)
            self._finished.set()

    def stop(self) -> None:
        super().stop()
        self._finished.set()
        self._audio.close()

    def cleanup(self) -> None:
        self._audio.close()

    def _read_source(self) -> None:
        try:
            for chunk in self._audio.chunks:
                # Read ahead a little, not the whole download into memory.
                while len(self._buffer) >= _MAX_BUFFERED and not self.is_stopped:
                    time.sleep(_BUFFER_POLL_SECONDS)
                if self.is_stopped:
                    break
                self._buffer.append(chunk)
        except Exception:
            pass  # a download cut off by `stop`, or failing: play what came
        finally:
            self._is_source_done = True

    def _fill(self, np: Any, sd: Any, out: Any, frames: int, info: Any = None) -> None:
        """The stream's callback: the next *frames* samples, or silence
        while paused or waiting for the download. They reach the speakers
        when the host says (``outputBufferDacTime``); a stream's start time
        drifts from its reported latency by tens of milliseconds from one
        utterance to the next, which would move the echo delay each time."""
        start = get_monotonic_time(
            getattr(info, "outputBufferDacTime", 0.0), getattr(info, "currentTime", 0.0)
        )
        if start is None:
            start = self._started_at + self._frames_elapsed / self._audio.sample_rate
        self._frames_elapsed += frames
        if self.is_stopped:
            out.fill(0)
            raise sd.CallbackStop
        if self._is_paused:
            out.fill(0)
            return
        wanted = frames * 2
        while len(self._pending) < wanted and self._buffer:
            self._pending += self._buffer.popleft()
        data, self._pending = self._pending[:wanted], self._pending[wanted:]
        samples = np.frombuffer(data, np.int16)
        out[: len(samples), 0] = samples
        out[len(samples) :, 0] = 0
        if len(samples):
            self._write_reference(np, samples, start)
        if not samples.size and self._is_source_done and not self._buffer:
            raise sd.CallbackStop

    def _write_reference(self, np: Any, samples: Any, start: float) -> None:
        rate = self._audio.sample_rate
        audio = samples.astype(np.float32) / 32768
        if rate != RATE:
            count = max(1, int(round(len(audio) * RATE / rate)))
            positions = np.linspace(0, len(audio) - 1, count)
            audio = np.interp(positions, np.arange(len(audio)), audio)
        self._reference.write(start, audio.astype(np.float32))


def _import_audio() -> tuple[Any, Any]:
    # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
    import numpy as np
    import sounddevice as sd

    return np, sd
