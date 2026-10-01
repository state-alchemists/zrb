"""Playing speech in zrb's own process, through sounddevice.

A `PcmUtterance` plays `SpeechAudio` through an output stream instead of a
player program, so playback can pause and resume: a cough heard over zrb
only stalls it for a moment.

It needs sounddevice and numpy (the zrb[voice] extra); `is_available` says
whether they import, and speech falls back to player programs when not.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from zrb.config.config import CFG
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.utterance import Utterance

# How long playback waits for the source reader to see it has ended.
_READER_JOIN_SECONDS = 1.0
_BUFFER_POLL_SECONDS = 0.005
# How often playback checks whether it is paused, to leave paused time out
# of the timeout.
_TIMEOUT_POLL_SECONDS = 0.02

logger = logging.getLogger(__name__)


@functools.cache
def is_available() -> bool:
    """Whether sounddevice and numpy import, so speech can play in process.
    Asked once per process; `is_available.cache_clear()` asks again."""
    try:
        _import_audio()
    except (ImportError, OSError):
        return False
    return True


class PcmUtterance(Utterance):
    """`SpeechAudio` played through a sounddevice output stream, in blocks of
    *block_frames* samples, reading *read_ahead* chunks ahead of playback;
    left ``None``, `CFG.LLM_SPEECH_PLAYER_BLOCK_FRAMES` and
    `CFG.LLM_SPEECH_PLAYER_READ_AHEAD`.

    When the output device cannot be opened (none, or busy), or the audio
    fails before any of it was heard (a download cut off, a broken stream),
    *fallback* makes the same speech for a player program to play instead,
    so it is not lost; without one, a device error is raised and a source
    error logged. Audio that fails part-way is played as far as it came,
    and logged as cut off. *on_device_error*, when given, is told of a
    device that cannot open instead of it being logged, so a caller can
    stop trying the device and say so once.

    The play timeout counts playing time only: a pause does not use it up.
    """

    def __init__(
        self,
        audio: SpeechAudio,
        block_frames: int | None = None,
        read_ahead: int | None = None,
        fallback: Callable[[], Utterance] | None = None,
        on_device_error: Callable[[Exception], None] | None = None,
    ):
        super().__init__([])
        self._fallback = fallback
        self._on_device_error = on_device_error
        # Guards `_fallback_playing` against `pause` and `stop`, which may
        # come from another thread while the fallback starts.
        self._fallback_lock = threading.Lock()
        self._fallback_playing: Utterance | None = None
        # Set once the device opened: a failure after that is not retried,
        # or the sentence would be heard twice.
        self._has_opened = False
        # Set when the device failed: ends the source reader without
        # counting as `stop`, which would also skip the fallback.
        self._is_abandoned = False
        # What made the source stop early, unless `stop` did.
        self._source_error: Exception | None = None
        self._has_played_audio = False
        if block_frames is None:
            block_frames = CFG.LLM_SPEECH_PLAYER_BLOCK_FRAMES
        if read_ahead is None:
            read_ahead = CFG.LLM_SPEECH_PLAYER_READ_AHEAD
        self._block_frames = max(1, block_frames)
        self._read_ahead = max(1, read_ahead)
        self._audio = audio
        self._buffer: deque[bytes] = deque()
        self._pending = b""
        self._is_source_done = False
        self._is_paused = False
        self._finished = threading.Event()

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_pausable(self) -> bool:
        """True, unless a player program took over (the fallback)."""
        return self._fallback_playing is None

    def pause(self) -> None:
        """Hold playback where it is; silence until `resume`. A player program
        playing the fallback cannot hold, so it is stopped, and a fallback
        not yet started is not played."""
        with self._fallback_lock:
            self._is_paused = True
            fallback_playing = self._fallback_playing
        if fallback_playing is not None:
            fallback_playing.stop()

    def resume(self) -> None:
        self._is_paused = False

    def play(self, timeout: float | None) -> None:
        """Play to the end, or until *timeout* seconds or `stop`; through
        the fallback when the device cannot be opened."""
        if self.is_stopped:
            return
        try:
            self._play_in_process(timeout)
        except Exception as exc:
            if self._has_opened or self._fallback is None or self.is_stopped:
                raise
            if self._on_device_error is not None:
                self._on_device_error(exc)
            else:
                logger.warning(
                    f"Could not open the audio device to play speech in process "
                    f"({exc}); a player program plays it instead"
                )
            self._play_fallback(self._fallback, timeout)
            return
        self._handle_source_error(timeout)

    def _handle_source_error(self, timeout: float | None) -> None:
        error = self._source_error
        if error is None or self.is_stopped:
            return
        if not self._has_played_audio and self._fallback is not None:
            logger.warning(
                f"Speech audio failed before any of it played ({error}); a "
                "player program plays it instead"
            )
            self._play_fallback(self._fallback, timeout)
            return
        logger.warning(f"Speech was cut off: its audio stopped arriving ({error})")

    def _play_fallback(
        self, fallback: Callable[[], Utterance], timeout: float | None
    ) -> None:
        utterance = fallback()
        utterance.set_on_start(self.report_started)
        with self._fallback_lock:
            self._fallback_playing = utterance
            # `stop` or `pause` may have come meanwhile: a program cannot
            # hold the speech, so a paused one is not started.
            is_held = self.is_stopped or self._is_paused
        try:
            if not is_held:
                utterance.play(timeout)
        finally:
            with self._fallback_lock:
                if self._fallback_playing is utterance:
                    self._fallback_playing = None
            utterance.cleanup()

    def _play_in_process(self, timeout: float | None) -> None:
        np, sd = _import_audio()
        reader = threading.Thread(target=self._read_source, daemon=True)
        is_played = False
        try:
            stream = sd.OutputStream(
                samplerate=self._audio.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self._block_frames,
                callback=lambda out, frames, info, status: self._fill(
                    np, sd, out, frames
                ),
                finished_callback=self._finished.set,
            )
            # Only once there is a stream to play into: a device that cannot
            # open must not leave a download running.
            reader.start()
            self._play_stream(stream, timeout)
            is_played = True
        finally:
            self._finished.set()
            if not is_played:
                # The device failed: close the source, which ends the read.
                self._is_abandoned = True
                self._audio.close()
            if reader.is_alive():
                reader.join(_READER_JOIN_SECONDS)

    def _play_stream(self, stream: Any, timeout: float | None) -> None:
        try:
            stream.start()
        except BaseException:
            stream.close()  # opened, never started: close it all the same
            raise
        try:
            self._has_opened = True
            self.report_started()
            if not self._is_finished_in_time(timeout):
                self.stop()
        finally:
            try:
                stream.stop()
            finally:
                stream.close()

    def _is_finished_in_time(self, timeout: float | None) -> bool:
        """Whether playback finished before *timeout* seconds of playing;
        paused time is not counted."""
        if timeout is None:
            self._finished.wait()
            return True
        played = 0.0
        last = time.monotonic()
        while not self._finished.wait(_TIMEOUT_POLL_SECONDS):
            now = time.monotonic()
            if not self._is_paused:
                played += now - last
            last = now
            if played >= timeout:
                return False
        return True

    def stop(self) -> None:
        super().stop()
        self._finished.set()
        self._audio.close()
        with self._fallback_lock:
            fallback_playing = self._fallback_playing
        if fallback_playing is not None:
            fallback_playing.stop()

    def cleanup(self) -> None:
        self._audio.close()

    def _read_source(self) -> None:
        try:
            for chunk in self._audio.chunks:
                # Read ahead a little, not the whole download into memory.
                while len(self._buffer) >= self._read_ahead and not self._is_done:
                    time.sleep(_BUFFER_POLL_SECONDS)
                if self._is_done:
                    break
                self._buffer.append(chunk)
        except Exception as exc:
            # A download cut off by `stop` is no failure; any other is, and
            # what came is still played.
            if not self._is_done:
                self._source_error = exc
        finally:
            self._is_source_done = True

    @property
    def _is_done(self) -> bool:
        return self.is_stopped or self._is_abandoned

    def _fill(self, np: Any, sd: Any, out: Any, frames: int) -> None:
        """The stream's callback: the next *frames* samples, or silence
        while paused or waiting for the download."""
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
            self._has_played_audio = True
        if not samples.size and self._is_source_done and not self._buffer:
            raise sd.CallbackStop


def _import_audio() -> tuple[Any, Any]:
    # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
    import numpy as np
    import sounddevice as sd

    return np, sd
