"""The microphone with zrb's own voice taken out, through macOS voice processing.

macOS cancels echo only for an app that asks: `AVAudioEngine`'s input node
in voice-processing mode. It cancels whatever the output device plays, so
zrb's voice keeps playing through its own sounddevice stream (ADR-0103) and
only capture moves here. Measured on a MacBook's own speakers and
microphone, zrb's words went from transcribed nearly whole to not at all,
while the user's voice over it stayed intact (ADR-0111).

`EchoCancelledMicrophone` stands in for the sounddevice input stream `listen`
otherwise opens: the same callback, the same blocks (mono float32 at the
transcriber's rate), ``active`` and ``close``. Linux needs no code: PulseAudio
and PipeWire cancel echo system-wide once their echo-cancel module is loaded.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sys
import threading
import time
from collections.abc import Callable
from types import ModuleType
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    import numpy
    from numpy.typing import NDArray

    Samples = NDArray[numpy.float32]

# Taps per side of the anti-aliasing filter run before downsampling.
_FILTER_HALF_TAPS = 32
# Where the filter cuts, as a fraction of the target rate's Nyquist frequency.
_FILTER_CUTOFF = 0.9
# How often `confirm_audio` looks for the first block.
_CONFIRM_POLL_SECONDS = 0.05

AudioCallback = Callable[["Samples", int, None, None], None]


def get_unavailable_reason(device: str | None) -> str | None:
    """Why echo cancellation cannot be used here, or ``None`` when it can."""
    if sys.platform != "darwin":
        return (
            "zrb asks for it only on macOS; on Linux, load PulseAudio's or "
            "PipeWire's echo-cancel module instead (see the voice docs)"
        )
    if device:
        return (
            f"{CFG.ENV_PREFIX}_LLM_DICTATION_DEVICE names a microphone, and "
            "macOS voice processing uses the system default one"
        )
    if importlib.util.find_spec("AVFoundation") is None:
        return "it needs pyobjc-framework-AVFoundation: pip install 'zrb[voice]'"
    return None


class Resampler:
    """Mono audio from *source_rate* to *target_rate*, a block at a time.

    Blocks may be any length; the output is what converting their
    concatenation in one go would give, give or take the filter's start-up,
    so block edges leave no seam. Downsampling first runs a windowed-sinc
    low-pass, so speech above the target's Nyquist frequency does not fold
    back into the band the transcriber hears.
    """

    def __init__(self, np: ModuleType, source_rate: float, target_rate: float) -> None:
        self._np = np
        self._step = source_rate / target_rate
        self._taps = self._create_filter(source_rate, target_rate)
        self._history = np.zeros(len(self._taps) - 1, dtype=np.float32)
        self._last = np.float32(0.0)
        self._consumed = 0  # filtered samples before the current block
        self._next = 0.0  # where the next output sample falls, in those

    def convert(self, block: Samples) -> Samples:
        """*block*, a 1-D float32 array, at the target rate."""
        np = self._np
        signal = np.concatenate((self._history, block.astype(np.float32)))
        filtered = np.convolve(signal, self._taps, mode="valid")
        self._history = signal[len(signal) - len(self._history) :]
        # The last sample of the previous block lets an output fall between
        # the two blocks.
        known = np.concatenate(([self._last], filtered))
        end = self._consumed + len(filtered) - 1
        positions = np.arange(self._next, end + 1e-9, self._step)
        out = np.interp(positions - (self._consumed - 1), np.arange(len(known)), known)
        if len(positions):
            self._next = float(positions[-1]) + self._step
        if len(filtered):
            self._last = filtered[-1]
        self._consumed += len(filtered)
        return out.astype(np.float32)

    def _create_filter(self, source_rate: float, target_rate: float) -> Samples:
        np = self._np
        if target_rate >= source_rate:
            return np.ones(1, dtype=np.float32)
        cutoff = _FILTER_CUTOFF * target_rate / source_rate  # of source Nyquist
        n = np.arange(-_FILTER_HALF_TAPS, _FILTER_HALF_TAPS + 1)
        taps = cutoff * np.sinc(cutoff * n) * np.hamming(len(n))
        return (taps / taps.sum()).astype(np.float32)


class Rechunker:
    """Audio of any block length handed on in blocks of exactly *blocksize*."""

    def __init__(
        self, np: ModuleType, blocksize: int, emit: Callable[[Samples], None]
    ) -> None:
        self._np = np
        self._blocksize = blocksize
        self._emit = emit
        self._pending = np.zeros(0, dtype=np.float32)

    def append(self, samples: Samples) -> None:
        """Add *samples*; every whole block they complete is emitted."""
        pending = self._np.concatenate((self._pending, samples))
        whole = len(pending) // self._blocksize * self._blocksize
        for start in range(0, whole, self._blocksize):
            self._emit(pending[start : start + self._blocksize])
        self._pending = pending[whole:]


class EchoCancelledMicrophone:
    """The default microphone through macOS voice processing.

    *callback* is called from the audio thread as sounddevice calls an input
    stream's: ``callback(indata, frames, time_info, status)``, *indata* a
    ``(blocksize, 1)`` float32 array at *samplerate*. ``time_info`` and
    ``status`` are ``None``; `listen` reads neither.
    """

    def __init__(
        self,
        np: ModuleType,
        callback: AudioCallback,
        samplerate: int,
        blocksize: int,
    ) -> None:
        self._np = np
        self._callback = callback
        self._samplerate = samplerate
        self._blocksize = blocksize
        # An `AVAudioEngine` once started; pyobjc ships no type stubs.
        self._engine = None
        self._lock = threading.Lock()
        self._has_audio = threading.Event()

    @property
    def is_active(self) -> bool:
        """Whether the engine is running; macOS stops it when the audio
        devices change, and `listen` then opens the microphone again."""
        engine = self._engine
        return bool(engine is not None and engine.isRunning())

    # sounddevice's name for it, which `listen` reads of either microphone.
    active = is_active

    def start(self) -> None:
        """Open the microphone in voice-processing mode, or raise
        `RuntimeError` saying why it would not start."""
        try:
            engine = self._start_engine()
        except RuntimeError:
            raise
        except Exception as e:  # pyobjc raises whatever Cocoa raised
            raise RuntimeError(
                f"The echo-cancelled microphone would not start: {e}"
            ) from e
        with self._lock:
            self._engine = engine

    async def confirm_audio(self, timeout: float) -> None:
        """Wait until the first block arrives, or raise `RuntimeError`.

        A started engine is not yet a working microphone: with a Bluetooth
        headset as the default device, macOS stops voice processing right
        after it starts, and no audio ever arrives. This says so at once
        when the engine stops, and after *timeout* seconds otherwise.
        """
        deadline = time.monotonic() + timeout
        while not self._has_audio.is_set():
            if not self.is_active or time.monotonic() >= deadline:
                raise RuntimeError(
                    "The echo-cancelled microphone heard nothing (macOS stops "
                    "voice processing on some devices, such as a Bluetooth "
                    "headset)"
                )
            await asyncio.sleep(_CONFIRM_POLL_SECONDS)

    def close(self) -> None:
        """Stop the engine and switch voice processing off."""
        with self._lock:
            engine, self._engine = self._engine, None
        if engine is not None:
            _release(engine)

    def _start_engine(self):  # an AVAudioEngine; pyobjc has no type stubs
        avf = import_avfoundation()
        engine = avf.AVAudioEngine.alloc().init()
        try:
            self._run_engine(avf, engine)
        except BaseException:
            # Voice processing, the tap or a half-started engine would keep
            # the microphone from the plain one opened in its place.
            _release(engine)
            raise
        return engine

    def _run_engine(self, avf: ModuleType, engine) -> None:  # an AVAudioEngine
        # The voice-processing unit is one input/output unit: its output side
        # fails to initialize (-10875) unless it exists before voice
        # processing is switched on.
        engine.outputNode()
        engine.mainMixerNode()
        node = engine.inputNode()
        is_enabled, error = node.setVoiceProcessingEnabled_error_(True, None)
        if not is_enabled:
            raise RuntimeError(f"macOS voice processing would not switch on: {error}")
        _reduce_ducking(avf, node)
        input_rate = node.outputFormatForBus_(0).sampleRate()
        frames = int(input_rate * self._blocksize / self._samplerate)
        node.installTapOnBus_bufferSize_format_block_(
            0, frames, None, self._create_tap(input_rate)
        )
        engine.prepare()
        is_started, error = engine.startAndReturnError_(None)
        if not is_started:
            raise RuntimeError(
                f"The echo-cancelled microphone would not start: {error}"
            )

    def _create_tap(self, input_rate: float):  # an AVAudioNodeTapBlock
        np = self._np
        resampler = Resampler(np, input_rate, self._samplerate)
        rechunker = Rechunker(np, self._blocksize, self._emit)

        def tap(buffer, when) -> None:  # an AVAudioPCMBuffer, an AVAudioTime
            frames = buffer.frameLength()
            # Every channel carries the same processed voice; take the first.
            channel = buffer.floatChannelData()[0]
            samples = np.frombuffer(channel.as_buffer(frames), dtype=np.float32)
            rechunker.append(resampler.convert(samples))
            self._has_audio.set()

        return tap

    def _emit(self, block: Samples) -> None:
        self._callback(block.reshape(-1, 1), len(block), None, None)


def import_avfoundation() -> ModuleType:
    """pyobjc's AVFoundation; only imported on macOS, once echo
    cancellation is asked for."""
    return importlib.import_module("AVFoundation")


def _release(engine) -> None:  # an AVAudioEngine; pyobjc has no type stubs
    """Take the tap off, stop *engine* and switch voice processing off. Each
    step runs even when one before it raised, and a failure is raised after
    them all, chained to whatever failure the caller was handling."""
    node = engine.inputNode()
    try:
        node.removeTapOnBus_(0)
    finally:
        try:
            engine.stop()
        finally:
            node.setVoiceProcessingEnabled_error_(False, None)


def _reduce_ducking(avf: ModuleType, node: object) -> None:
    """Keep voice processing from turning down other apps' audio.

    It ducks by default; the minimum still cancels zrb's voice as well
    (measured), and spares the user's music and calls. macOS before 14 has
    no setting for it.
    """
    configure = getattr(node, "setVoiceProcessingOtherAudioDuckingConfiguration_", None)
    if configure is None:
        return
    configure((False, avf.AVAudioVoiceProcessingOtherAudioDuckingLevelMin))
