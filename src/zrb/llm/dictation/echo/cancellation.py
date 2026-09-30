"""Lining the microphone up with what zrb played, and cancelling it.

An echo canceller subtracts zrb's voice only if it is handed the audio zrb
played at the moment the microphone heard it. The latency the audio driver
reports cannot be trusted for that (PortAudio reported 705 ms of input
latency on a MacBook whose real echo delay is 49 ms), so `EchoCancellation`
measures the delay from the audio itself, the way WebRTC does: it
cross-correlates the last few seconds of microphone audio with what was
played, and reads the reference that far back, plus a small lead so the
reference is never late (an echo that arrives before its reference cannot be
subtracted).

Microphone blocks are timed by counting samples from the stream's start, not
by when each callback ran: callback timing wobbles by milliseconds, which the
canceller would take for a room that keeps changing.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller
from zrb.llm.speech.echo_reference import RATE, EchoReference, echo_reference

# The reference is read this far ahead of the measured delay, so it always
# leads the echo; the canceller's filter covers the difference.
_LEAD_SECONDS = 0.04
# Delays searched: the reported latencies of both streams can be off either
# way by hundreds of milliseconds.
_MIN_DELAY_SECONDS = -0.5
_MAX_DELAY_SECONDS = 1.0
# How much audio each estimate correlates, and how often one is made.
_WINDOW_SECONDS = 2.0
_ESTIMATE_EVERY_SECONDS = 1.0
# A correlation peak this strong, standing this far above the rest, is the
# echo and not chance; two estimates this close agree.
_MIN_PEAK = 0.05
_MIN_PEAK_RATIO = 6.0
_AGREE_SECONDS = 0.003
# A measured delay this far from the one in use is a new echo path (another
# output device) and starts the canceller over. Less is clock drift and
# measurement wobble, which the canceller follows on its own: the reference
# already leads by _LEAD_SECONDS and the filter covers far more.
_RELOCK_SECONDS = 0.025
_MIN_REFERENCE_RMS = 0.01
# Ready once, over this many recent blocks of zrb speaking, at most
# _MAX_LOUD_LEFTOVERS left anything at or over the level that starts an
# utterance: what is left of zrb's voice then cannot pass for the user.
_READY_WINDOW_BLOCKS = 20
_MAX_LOUD_LEFTOVERS = 1
_PLAYING_RMS = 0.005


class EchoCancellation:
    """*canceller* fed with the reference lined up to each microphone block."""

    def __init__(
        self,
        canceller: AnyEchoCanceller,
        reference: EchoReference | None = None,
        threshold: float = 0.01,
    ) -> None:
        """*threshold* is the microphone level that starts an utterance
        (``DictationConfig.threshold``)."""
        self._canceller = canceller
        self._threshold = threshold
        self._leftovers: list[bool] = []  # per block of zrb speaking: loud?
        self._is_ready = False
        self._reference = reference or echo_reference
        self._np = _numpy()
        self._mic_history = self._np.zeros(
            int(RATE * _WINDOW_SECONDS), self._np.float32
        )
        self._history_end = 0.0  # when the newest sample in it was captured
        self._delay: float | None = None
        self._candidate: float | None = None
        self._since_estimate = 0.0

    @property
    def canceller(self) -> AnyEchoCanceller:
        return self._canceller

    @property
    def delay(self) -> float | None:
        """The measured echo delay in seconds, once known."""
        return self._delay

    @property
    def is_ready(self) -> bool:
        """Whether what is left of zrb's voice can be told from the user:
        the delay is known, the canceller has converged, and what it left of
        zrb's recent speech stayed under the level that starts an utterance.
        Once ready it stays so, since the user talking over zrb is loud on
        purpose, until the echo path changes. One that needs no reference
        (``none``) is always ready."""
        if not self._canceller.needs_reference:
            return True
        return self._is_ready

    def process(self, mic: Any, start_time: float) -> Any:
        """*mic* (float32, 16 kHz), captured from *start_time* on, with zrb's
        echo removed."""
        np = self._np
        if not self._canceller.needs_reference:
            return self._canceller.process(mic, np.zeros(len(mic), np.float32))
        self._remember(mic, start_time)
        if self._delay is None:
            far = np.zeros(len(mic), np.float32)
        else:
            far = self._reference.read(
                start_time - self._delay + _LEAD_SECONDS, len(mic)
            )
        out = self._canceller.process(mic, far)
        self._judge_leftover(far, out)
        return out

    def _judge_leftover(self, far: Any, out: Any) -> None:
        np = self._np
        if self._is_ready or self._delay is None:
            return
        if float(np.sqrt(np.mean(far**2))) < _PLAYING_RMS:
            return  # zrb silent here: nothing to judge
        self._leftovers = self._leftovers[-(_READY_WINDOW_BLOCKS - 1) :] + [
            float(np.sqrt(np.mean(out**2))) >= self._threshold
        ]
        if (
            self._canceller.is_converged
            and len(self._leftovers) >= _READY_WINDOW_BLOCKS
            and sum(self._leftovers) <= _MAX_LOUD_LEFTOVERS
        ):
            self._is_ready = True

    def _remember(self, mic: Any, start_time: float) -> None:
        np = self._np
        self._mic_history = np.concatenate([self._mic_history[len(mic) :], mic])
        self._history_end = start_time + len(mic) / RATE
        self._since_estimate += len(mic) / RATE
        if self._since_estimate >= _ESTIMATE_EVERY_SECONDS:
            self._since_estimate = 0.0
            self._update_delay(self._estimate_delay())

    def _estimate_delay(self) -> float | None:
        """The delay at which the microphone best matches what was played
        (GCC-PHAT), or ``None`` without a clear answer."""
        np = self._np
        mic = self._mic_history
        window_start = self._history_end - len(mic) / RATE
        # Reference covering every delay searched: played up to
        # _MAX_DELAY_SECONDS before the window, or up to -_MIN_DELAY after.
        far_start = window_start - _MAX_DELAY_SECONDS
        far_length = len(mic) + int(RATE * (_MAX_DELAY_SECONDS - _MIN_DELAY_SECONDS))
        far = self._reference.read(far_start, far_length)
        if float(np.sqrt(np.mean(far**2))) < _MIN_REFERENCE_RMS:
            return None
        size = 1 << int(np.ceil(np.log2(len(mic) + far_length)))
        cross = np.fft.rfft(mic, size) * np.conj(np.fft.rfft(far, size))
        correlation = np.fft.irfft(cross / (np.abs(cross) + 1e-12), size)
        # mic[t] matching far[t + offset]: offset = (_MAX - delay) * RATE.
        offsets = np.arange(0, int(RATE * (_MAX_DELAY_SECONDS - _MIN_DELAY_SECONDS)))
        values = correlation[(-offsets) % size]
        best = int(np.argmax(values))
        peak = float(values[best])
        typical = float(np.mean(np.abs(values))) + 1e-12
        if peak < _MIN_PEAK or peak / typical < _MIN_PEAK_RATIO:
            return None
        return _MAX_DELAY_SECONDS - offsets[best] / RATE

    def _update_delay(self, estimate: float | None) -> None:
        """Take *estimate* once a second one agrees with it. After that, only
        a delay that jumps (another output device) is taken, and starts the
        canceller over; drift is left to the canceller."""
        if estimate is None:
            return
        candidate, self._candidate = self._candidate, estimate
        if candidate is None or abs(candidate - estimate) > _AGREE_SECONDS:
            return
        if self._delay is None:
            self._delay = estimate
        elif abs(self._delay - estimate) > _RELOCK_SECONDS:
            self._canceller.reset()
            self._delay = estimate
            self._is_ready = False
            self._leftovers = []


def _numpy() -> Any:
    # lazy: heavy third-party (numpy is a zrb[voice] extra); built only when
    # barge-in is on, which needs the microphone anyway.
    import numpy

    return numpy
