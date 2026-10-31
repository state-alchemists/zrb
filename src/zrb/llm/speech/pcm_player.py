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
from zrb.llm.speech.any_output_stream import AnyOutputStream
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.util.audio_devices import (
    read_portaudio_default_output,
    read_system_default_output,
)
from zrb.llm.util.portaudio_exit import guard_portaudio_exit
from zrb.llm.util.priority import raise_priority

# How long playback waits for the source reader to see it has ended.
_READER_JOIN_SECONDS = 1.0
# How long a reader or prebuffer may wait before re-checking what it waits
# on, without a notify.
_BUFFER_POLL_SECONDS = 0.005
# Audio to have read ahead before the device starts playing, and how long
# holding it off for that at all is worth; past the wait, what came goes, and
# a sentence that never starts is worse than one that stutters in its first
# block. The cushion itself is a setting
# (`CFG.LLM_SPEECH_PLAYER_PREBUFFER_SECONDS`): a slower engine needs more of
# it, and pays for it in the pause before each sentence's first word. The wait
# grows with the cushion, or it would cap a longer one back to itself and the
# setting would silently under-deliver where it is needed most.
_PREBUFFER_WAIT_FLOOR_SECONDS = 1.0
_PREBUFFER_WAIT_FACTOR = 2.0
# How often playback checks whether it is paused, to leave paused time out
# of the timeout.
_TIMEOUT_POLL_SECONDS = 0.02
# How long stopping and closing an output stream may take. It takes
# milliseconds; past this the operating system's audio service is wedged (a
# CoreAudio deadlock between PortAudio's audio thread and the stopping one), and
# the stream is given up on rather than left to hold the playing thread, the
# speaker and the exit of the process.
STREAM_STOP_TIMEOUT_SECONDS = 2.0

# The volume zrb speaks at, as a percentage of the speech's own level.
# `FULL_VOLUME` is the level the backend rendered; a lower one is quieter, a
# higher one louder until a sample no longer fits and has to clip.
MIN_VOLUME = 0
MAX_VOLUME = 200
FULL_VOLUME = 100
# What a 16-bit sample can hold, the ends a scaled one is clipped to.
_SAMPLE_MIN = -32768
_SAMPLE_MAX = 32767


def clamp_volume(percent: int) -> int:
    """*percent* held inside what zrb speaks at, ``MIN_VOLUME``-``MAX_VOLUME``."""
    return max(MIN_VOLUME, min(MAX_VOLUME, percent))


def prebuffer_wait_seconds(prebuffer_seconds: float) -> float:
    """How long holding playback off for *prebuffer_seconds* of audio is worth:
    twice the cushion, and never under `_PREBUFFER_WAIT_FLOOR_SECONDS`."""
    return max(
        _PREBUFFER_WAIT_FLOOR_SECONDS, prebuffer_seconds * _PREBUFFER_WAIT_FACTOR
    )


logger = logging.getLogger(__name__)

# Output streams between being created and being closed. PortAudio's own exit
# handler stops every stream still open, and on macOS two threads stopping one
# CoreAudio stream at once deadlock, so what ends a process waits on this first.
_streams_changed = threading.Condition()
_open_streams = 0


class _Captured:
    """Holds the exception raised inside a ``with`` block instead of raising
    it there, so a thread can hand it to the one waiting on it."""

    def __init__(self) -> None:
        self.error: BaseException | None = None

    def __enter__(self) -> "_Captured":
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> bool:
        self.error = exc
        return exc is not None


def _stream_opened() -> None:
    global _open_streams
    with _streams_changed:
        _open_streams += 1


def _stream_closed() -> None:
    global _open_streams
    with _streams_changed:
        _open_streams -= 1
        _streams_changed.notify_all()


def has_open_streams() -> bool:
    """Whether an output stream is still open: playing, or being stopped."""
    with _streams_changed:
        return _open_streams > 0


def wait_for_streams_to_close(timeout: float) -> None:
    """Wait up to *timeout* seconds for every output stream to be stopped and
    closed; `has_open_streams` says whether any is left. Call it once playback
    has been told to stop and before the process lets PortAudio terminate."""
    with _streams_changed:
        _streams_changed.wait_for(lambda: _open_streams == 0, timeout)


# The machine's default output when a sentence last opened a stream: PortAudio
# opens the default it read when it was started, so a stream on the wrong device
# is only noticed by comparing the two.
_default_output: str | None = None


def _start_portaudio_again(sd: object) -> None:
    """Start PortAudio again, so the devices and their defaults are read anew.

    It holds what it found when it was started, and never reads it again, which
    a headset plugged in or unplugged outdates: opening the default output then
    names a device that is gone, or opens the one that was the default before.
    The machine's default output at that moment is remembered as the one a
    stream now opens on. Nothing is done while an output stream is open, since
    starting PortAudio again stops every stream it has, nor when *sd* cannot do
    it (a fake, or a sounddevice too old to be asked). A start that fails is the
    caller's to report: it came to read the devices, and they were not read. A
    microphone open through PortAudio stops with it, which dictation reopens."""
    global _default_output
    terminate = getattr(sd, "_terminate", None)
    initialize = getattr(sd, "_initialize", None)
    if terminate is None or initialize is None:
        return
    with _streams_changed:
        if _open_streams:
            return
    terminate()
    initialize()
    _default_output = read_system_default_output(sd)


def _follow_the_default_output(sd: object) -> None:
    """Start PortAudio again when the machine's default output is not the one
    PortAudio opens without being asked for a device.

    A headset put back in is made the default output by macOS and is in no list
    PortAudio has, so without this the next sentence plays on whatever was the
    default when PortAudio started — the laptop speakers, say — for as long as
    the process lasts. The machine's default is read for every sentence, and
    the one a stream last opened on is remembered, so that a disagreement a
    restart does not settle (PortAudio naming a device its own way) is read
    again once, not for every sentence after."""
    global _default_output
    name = read_system_default_output(sd)
    if name is None or name == _default_output:
        return
    if read_portaudio_default_output(sd) != name:
        _start_portaudio_again(sd)
        return
    _default_output = name


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
    *block_frames* samples, reading *read_ahead* chunks ahead of playback and
    starting on *prebuffer_seconds* of audio; each left ``None``,
    `CFG.LLM_SPEECH_PLAYER_BLOCK_FRAMES`,
    `CFG.LLM_SPEECH_PLAYER_READ_AHEAD` and
    `CFG.LLM_SPEECH_PLAYER_PREBUFFER_SECONDS`. The cushion buys a slow engine
    the time to make its next block, at the cost of that pause before each
    sentence starts.

    When the output device cannot be opened (none, or busy), or the audio
    fails before any of it was heard (a download cut off, a broken stream),
    *fallback* makes the same speech for a player program to play instead,
    so it is not lost; without one, a device error is raised and a source
    error logged. Audio that fails part-way is played as far as it came,
    and logged as cut off. *on_device_error*, when given, is told of a
    device that cannot open instead of it being logged, so a caller can keep
    the next sentences off the device for a moment and say so once; it is
    told even when no fallback can take the sentence over. *device_is_resting*,
    when given, is asked just before the device is opened: while it says the
    device rests, *fallback* speaks instead, so a sentence made before the
    failure does not open the device either.

    A device PortAudio stops playing on its own (it was unplugged, or stopped
    being the output while its old stream was dropped) ends the sentence the
    same way, and the next one reopens on whatever is the output then. What
    PortAudio holds as its devices is from when it was started, so a device
    that rests is opened on a PortAudio started again, which reads the devices
    the machine has now; an open that fails is tried once more the same way,
    and so is a sentence made while the machine's default output moved — a
    headset put back in, say — which PortAudio would not have noticed.

    Blocks the device asks for before the audio arrives, or that arrive
    late (`underruns`, what the listener hears as stutter), are counted and
    said once.

    *volume* is a percentage of the audio's own level, 0-200, fixed when the
    utterance is made: what plays is the backend's samples scaled, clipped at
    the ends a 16-bit sample has.

    *prebuffer_seconds* is how much audio stands by before the device starts.
    It is the newest of these, and sits last for that reason: an older caller
    passing the others by position still means what it meant.

    The play timeout counts playing time only: a pause does not use it up.
    """

    def __init__(
        self,
        audio: SpeechAudio,
        block_frames: int | None = None,
        read_ahead: int | None = None,
        fallback: Callable[[], Utterance] | None = None,
        on_device_error: Callable[[Exception], None] | None = None,
        device_is_resting: Callable[[], bool] | None = None,
        volume: int = FULL_VOLUME,
        prebuffer_seconds: float | None = None,
    ):
        super().__init__([])
        self._fallback = fallback
        self._on_device_error = on_device_error
        self._resting_device_check = device_is_resting
        # Fixed when the utterance is made: a sentence already being spoken
        # keeps the level it started with, rather than fading mid-word.
        self._volume = clamp_volume(volume)
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
        self._said_end = False
        self._said_end_lock = threading.Lock()
        self._underruns = 0
        # An underrun the callback counted, and whether it was said, live
        # with the playing thread: the callback cannot log, the monitor can.
        self._underruns_pending = False
        self._underruns_logged = False
        if block_frames is None:
            block_frames = CFG.LLM_SPEECH_PLAYER_BLOCK_FRAMES
        if read_ahead is None:
            read_ahead = CFG.LLM_SPEECH_PLAYER_READ_AHEAD
        if prebuffer_seconds is None:
            prebuffer_seconds = CFG.LLM_SPEECH_PLAYER_PREBUFFER_SECONDS
        self._block_frames = max(1, block_frames)
        self._read_ahead = max(1, read_ahead)
        # No cushion means the device starts as soon as anything at all has
        # arrived, which is a setting someone may choose; a negative one is
        # not, and reads the same way.
        self._prebuffer_seconds = max(0.0, prebuffer_seconds)
        self._prebuffer_wait_seconds = prebuffer_wait_seconds(self._prebuffer_seconds)
        self._audio = audio
        self._buffer: deque[bytes] = deque()
        # The audio in `_buffer`, in bytes; both it and `_is_source_done`
        # answer to `_buffer_changed`, whose waiters are the reader and the
        # prebuffer to play.
        self._buffer_bytes = 0
        self._buffer_changed = threading.Condition()
        self._pending = b""
        self._is_source_done = False
        self._is_paused = False
        self._finished = threading.Event()

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def underruns(self) -> int:
        """How many blocks this playback could not fill with audio in time:
        the stutter the listener heard."""
        return self._underruns

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
        the fallback when the device cannot be opened, or rests."""
        if self.is_stopped:
            self._heard(b"")
            return
        fallback = self._fallback
        if fallback is not None and self._is_device_resting():
            # The device failed moments ago: opening it again would fail the
            # same way, however long ago this sentence was made.
            self._play_fallback(fallback, timeout)
            return
        try:
            self._play_in_process(timeout)
        except Exception as exc:
            # Said even where nothing takes the sentence over: it is the device
            # that failed, and the sentence after it must not open that device
            # as though it were still there.
            self._report_device_error(
                exc, "Could not open the audio device to play speech in process"
            )
            if self._has_opened or self._fallback is None or self.is_stopped:
                raise
            self._play_fallback(self._fallback, timeout)
            return
        self._handle_source_error(timeout)

    def _report_device_error(self, exc: Exception, in_the_log: str) -> None:
        """Tell the caller the device could not play this, or say it here, as
        *in_the_log*."""
        if self._on_device_error is not None:
            self._on_device_error(exc)
        else:
            logger.warning(f"{in_the_log}: {exc}")

    def _is_device_resting(self) -> bool:
        """Whether the caller says the device is being left alone for now."""
        is_resting = self._resting_device_check
        return is_resting is not None and is_resting()

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
        reader = threading.Thread(target=self._read_source, daemon=True)
        is_played = False
        try:
            stream = self._open_stream()
            try:
                # Only once there is a stream to play into: a device that
                # cannot open must not leave a download running.
                reader.start()
            except BaseException:
                self._close_unplayed(stream.close)
                raise
            self._play_stream(stream, timeout)
            is_played = True
        finally:
            self._finished.set()
            # The stream is stopped by now, so no callback can still be
            # sending blocks: the end is said here, in order after them, even
            # when `stop` came between two callbacks and `_fill` never ran
            # again. `_heard` says it once. Only for a sentence that was heard
            # or stopped: a device that failed to open played nothing, and the
            # fallback is about to say the sentence, so no end is announced.
            if self._has_played_audio or self.is_stopped:
                self._heard(b"")
            if not is_played:
                # The device failed: close the source, which ends the read.
                self._is_abandoned = True
                self._audio.close()
                with self._buffer_changed:
                    self._buffer_changed.notify_all()
            if reader.is_alive():
                reader.join(_READER_JOIN_SECONDS)

    def _open_stream(self) -> "AnyOutputStream":
        """The output stream, on the device the machine has now.

        PortAudio holds the devices, and the default output, that it found when
        it was started, and never reads them again: a headset unplugged after
        that leaves the default naming a device that is gone, and one put back
        in is not in its list at all. Reading them again is what lets a
        sentence keep its own voice across a change of output, instead of going
        unsaid or being said into the laptop speakers a headset was unplugged
        from."""
        _, sd = _import_audio()
        is_resting = self._is_device_resting()
        if is_resting:
            _start_portaudio_again(sd)
        else:
            _follow_the_default_output(sd)
        try:
            return self._build_stream()
        except Exception:
            # The devices were read again before this attempt when the device
            # rests: there is no older list left to correct.
            if is_resting:
                raise
        _start_portaudio_again(sd)
        return self._build_stream()

    def _build_stream(self) -> "AnyOutputStream":
        # Counted as open from before it is built (a constructed
        # `OutputStream` is already an open PortAudio stream, so the exit
        # handler must see it from the moment it exists) until it has actually
        # been closed, which `_stop_stream` says.
        np, sd = _import_audio()
        _stream_opened()
        try:
            return sd.OutputStream(
                samplerate=self._audio.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self._block_frames,
                callback=lambda out, frames, info, status: self._fill(
                    np, out, frames, status
                ),
                finished_callback=self._finished.set,
            )
        except BaseException:
            _stream_closed()
            raise

    def _close_unplayed(self, close: Callable[[], object]) -> None:
        """Close a stream that was opened and never played."""
        try:
            close()
        finally:
            _stream_closed()

    def _play_stream(self, stream: Any, timeout: float | None) -> None:
        # Nothing is heard until the device starts: starting it on audio in
        # hand keeps the first block from being silence.
        self._prebuffer()
        try:
            if self._is_done:
                self._close_unplayed(stream.close)
                return
            stream.start()
        except BaseException:
            self._close_unplayed(stream.close)  # never started: close it all the same
            raise
        try:
            self._has_opened = True
            self.report_started()
            if not self._is_finished_in_time(timeout, stream):
                self.stop()
            # An underrun in the block that finished the playback (the wait
            # was over before another poll of it) is still said.
            self._say_pending_underruns()
        finally:
            self._stop_stream(stream.stop, stream.close)

    def _prebuffer(self) -> None:
        """Wait until a moment of audio stands by to play (`_is_source_done`
        and `stop` release the wait), so the device's first block has sound."""
        ready = self._prebuffer_bytes()
        with self._buffer_changed:
            self._buffer_changed.wait_for(
                lambda: self._buffer_bytes >= ready
                or self._is_source_done
                or self._is_done,
                timeout=self._prebuffer_wait_seconds,
            )

    def _prebuffer_bytes(self) -> int:
        """How much audio must stand by before the device starts, in bytes: the
        cushion, and at least one byte of it — a cushion of zero starts on
        whatever has arrived, and a device fed an empty block opens the
        sentence on silence the listener hears as a stutter."""
        return max(1, int(self._audio.sample_rate * self._prebuffer_seconds) * 2)

    def _stop_stream(
        self, stop: Callable[[], object], close: Callable[[], object]
    ) -> None:
        """Stop and close a stream, through *stop* and *close*, on a thread of
        its own, and give up on it if that does not finish in time.

        On macOS, stopping a stream can deadlock inside CoreAudio: the audio
        thread, in PortAudio's start-stop callback, and the stopping thread
        each wait for a lock the other holds. Nothing can be done about that
        from here, so it must not be allowed to freeze the thread that plays
        speech, which every later sentence waits on."""
        done = threading.Event()
        captured = _Captured()

        def run() -> None:
            try:
                with captured:
                    try:
                        stop()
                    finally:
                        close()
            finally:
                # Only now is the stream closed. Abandoned by the wait below,
                # it stays counted until this thread is done with it, so
                # nothing at exit takes it for gone.
                _stream_closed()
                done.set()

        threading.Thread(target=run, name="zrb-speech-stop", daemon=True).start()
        if not done.wait(STREAM_STOP_TIMEOUT_SECONDS):
            self._abandon_stream()
        elif captured.error is not None:
            raise captured.error

    def _abandon_stream(self) -> None:
        """Stop waiting for a stream that will not stop, and say so.

        What was being said is not lost by this: the stream is only stopped once
        its audio has played to the end, or on purpose (`stop`, a timeout), so
        handing the sentence to a player program as well would say it twice.
        Later sentences go to the program until the device is tried again."""
        error = TimeoutError(
            f"stopping the output stream took over {STREAM_STOP_TIMEOUT_SECONDS} "
            "seconds; the audio service is stuck"
        )
        guard_exit_handler()
        if self._on_device_error is not None:
            self._on_device_error(error)
        else:
            logger.warning(f"Giving up on the speech stream: {error}")

    def _is_finished_in_time(self, timeout: float | None, stream: object) -> bool:
        """Whether playback finished before *timeout* seconds of playing,
        paused time is not counted, and the device itself kept playing.

        PortAudio stops the stream when its device is gone (a headset
        unplugged, or no longer being the output as another one was made
        default with the hand-over's dead stream dropped): the sentence ends
        there, what was heard was heard, and the next one opens on whatever
        is the device then. Its finished callback sets `_finished` too, so
        the wait answering is not by itself an end that was played to."""
        played = 0.0
        last = time.monotonic()
        while not self._finished.wait(_TIMEOUT_POLL_SECONDS):
            self._say_pending_underruns()
            now = time.monotonic()
            if not self._is_paused:
                played += now - last
            last = now
            if timeout is not None and played >= timeout:
                return False
            if not getattr(stream, "active", False):
                self._note_the_device_lost()
                self._finished.set()
        # The wait is over, but not every end of it was played to: PortAudio
        # can have stopped the stream itself — its finished callback set
        # `_finished` before the loop had a look at the device.
        if not self.is_stopped and not getattr(stream, "active", False):
            self._note_the_device_lost()
        return True

    def _note_the_device_lost(self) -> None:
        """A stream PortAudio stopped on its own — its device was unplugged,
        or stopped being the output while the hand-over dropped the old
        stream: the sentence is cut off, what was heard was heard, and the
        source is closed (`_is_abandoned`, not `stop`), which ends the read
        that would otherwise keep running behind a device that is gone.
        Said once: the monitor that saw it and the look after its wait can
        both come here for the same dead stream.

        The caller hears of it too, even with nothing left to play: the next
        sentence has to open the devices the machine has now, not the ones
        PortAudio was started with."""
        if self._is_abandoned:
            return
        self._source_error = RuntimeError(
            "the output stream stopped playing on its own (the audio "
            "device may have been unplugged or changed)"
        )
        self._report_device_error(self._source_error, "Speech was cut off")
        self._is_abandoned = True
        self._audio.close()
        with self._buffer_changed:
            self._buffer_changed.notify_all()
        if self._has_played_audio or self._fallback is None:
            # What was heard was heard: the saying was done here, and the
            # source error would only have the handler say it again. A
            # sentence nothing of was heard keeps it, for the handler to
            # hand it to a player program.
            self._source_error = None

    def stop(self) -> None:
        super().stop()
        self._finished.set()
        self._audio.close()
        with self._buffer_changed:
            self._buffer_changed.notify_all()
        with self._fallback_lock:
            fallback_playing = self._fallback_playing
        if fallback_playing is not None:
            fallback_playing.stop()

    def cleanup(self) -> None:
        self._audio.close()

    def _read_source(self) -> None:
        raise_priority()
        try:
            for chunk in self._audio.chunks:
                # Read ahead a little, not the whole download into memory.
                if not self._has_room_for_a_chunk():
                    break
                with self._buffer_changed:
                    self._buffer.append(chunk)
                    self._buffer_bytes += len(chunk)
                    self._buffer_changed.notify_all()
        except Exception as exc:
            # A download cut off by `stop` is no failure; any other is, and
            # what came is still played.
            if not self._is_done:
                self._source_error = exc
        finally:
            with self._buffer_changed:
                self._is_source_done = True
                self._buffer_changed.notify_all()

    def _has_room_for_a_chunk(self) -> bool:
        """Whether another chunk may be appended: waits for the read ahead
        (`_read_ahead`) to have room, and is false only once playback was
        stopped.

        The read ahead is a count and the cushion is a duration, so the count
        does not bound it: chunks differ in size, and a backend that streams
        them small would never hold a cushion counted in seconds — the reader
        would stop at `_read_ahead` chunks, the prebuffer would wait out its
        timeout for audio nothing was reading, and the sentence would start
        under the cushion it was given. Standing the cushion by comes first;
        past it, the count keeps the download out of memory."""
        cushion = self._prebuffer_bytes()
        with self._buffer_changed:
            while (
                len(self._buffer) >= self._read_ahead
                and self._buffer_bytes >= cushion
                and not self._is_done
            ):
                self._buffer_changed.wait(_BUFFER_POLL_SECONDS)
            return not self._is_done

    @property
    def _is_done(self) -> bool:
        return self.is_stopped or self._is_abandoned

    def _fill(self, np: Any, out: Any, frames: int, status: object) -> None:
        """The stream's callback: the next *frames* samples, or silence
        while paused, waiting for the download, or finished. *status* is
        PortAudio's own word on whether the device got its audio in time
        (`output_underflow`).

        It never raises `sd.CallbackStop`. PortAudio answers that by stopping
        the stream from its own audio thread, while the thread playing the
        utterance stops the same stream once `_finished` is set; two threads
        stopping one CoreAudio stream deadlock. Only the playing thread stops
        the stream, so the callback only says it is done, by setting
        `_finished`."""
        if self.is_stopped:
            out.fill(0)
            self._finished.set()
            self._heard(b"")
            return
        if self._is_paused:
            out.fill(0)
            return
        wanted = frames * 2
        with self._buffer_changed:
            while len(self._pending) < wanted and self._buffer:
                chunk = self._buffer.popleft()
                self._buffer_bytes -= len(chunk)
                self._pending += chunk
                self._buffer_changed.notify_all()
            data, self._pending = self._pending[:wanted], self._pending[wanted:]
            is_source_done = self._is_source_done
        samples = np.frombuffer(data, np.int16)
        if self._volume != FULL_VOLUME:
            # Integer, not float: a sample at FULL_VOLUME must come back
            # bit-identical rather than re-rounded, and this runs in PortAudio's
            # real-time callback. Clipped, because above FULL_VOLUME a loud
            # sample has nowhere to go, and wrapping it into the opposite sign is
            # heard as a crackle.
            scaled = samples.astype(np.int32) * self._volume // FULL_VOLUME
            np.clip(scaled, _SAMPLE_MIN, _SAMPLE_MAX, out=scaled)
            samples = scaled.astype(np.int16)
        out[: len(samples), 0] = samples
        out[len(samples) :, 0] = 0
        if len(samples):
            self._has_played_audio = True
            # What the device gets, after volume and clipping, not what was read.
            self._heard(samples.tobytes())
        if getattr(status, "output_underflow", False) or (
            samples.size < frames and not is_source_done
        ):
            self._note_underrun()
        if not samples.size and is_source_done and not self._buffer:
            self._finished.set()
            self._heard(b"")

    def _heard(self, block: bytes) -> None:
        """Tell whoever listens to the voice that *block* is being heard now.

        `SpeechAudio.on_block`: the blocks as they reach the device, and one
        empty block when there are no more (played to the end, or stopped
        before it). Reading the chunks is not this moment -- the player keeps
        seconds of them standing by -- which is what makes it the right signal
        for a mouth or a caption.

        This runs on PortAudio's real-time callback, where being late is
        heard as a stutter, so it does the least it can: one call, no waiting.
        A listener that raises is not allowed to take the sentence down with
        it, so the exception ends the listening rather than the playback."""
        heard = self._audio.on_block
        if heard is None:
            return
        if not block:
            with self._said_end_lock:
                if self._said_end:
                    return
                self._said_end = True
        elif self._said_end:
            return
        try:
            heard(block)
        except Exception:  # a listener's bug must not silence the voice
            pass

    def _note_underrun(self) -> None:
        """Count one block the playback could not fill with audio in time,
        what the listener hears as stutter. Only the count lives here: the
        saying of it runs where logging cannot block this (real-time)
        callback, whose lateness would underrun again."""
        self._underruns += 1
        self._underruns_pending = True

    def _say_pending_underruns(self) -> None:
        """Say an underrun the audio callback counted that no one has said
        yet; the playing thread runs this, off the callback. Once is said:
        the count (`underruns`) carries the rest, and a stutter repeated is
        not another reason to say why."""
        if not self._underruns_pending:
            return
        self._underruns_pending = False
        if self._underruns_logged:
            return
        self._underruns_logged = True
        logger.warning(
            f"Speech stuttered: {self._underruns} block(s) of audio were not "
            "standing by in time (the audio arrives slowly, or the machine "
            f"cannot fill a block of {self._block_frames} frames from one "
            "callback to the next; "
            f"{CFG.ENV_PREFIX}_LLM_SPEECH_PLAYER_PREBUFFER_SECONDS starts each "
            "sentence on more audio, and "
            f"{CFG.ENV_PREFIX}_LLM_SPEECH_PLAYER_BLOCK_FRAMES makes the block "
            "longer to wait for)"
        )


def guard_exit_handler() -> None:
    """Keep sounddevice's exit handler from holding the process; see
    `guard_portaudio_exit`."""
    try:
        _, sd = _import_audio()
    except (ImportError, OSError):
        return
    guard_portaudio_exit(sd)


def _import_audio() -> tuple[Any, Any]:
    # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
    import numpy as np
    import sounddevice as sd

    return np, sd
