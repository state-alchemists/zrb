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

Microphone blocks are timed by when the host says their first sample was
captured (``inputBufferAdcTime``), or, where it gives no times, by counting
samples on from the previous block: when each callback ran wobbles by
milliseconds, which the canceller would take for a room that keeps changing.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller
from zrb.llm.speech.echo_reference import RATE, EchoReference, echo_reference

# Played audio kept beyond what one delay estimate reads.
_REFERENCE_MARGIN_SECONDS = 1.0


class EchoCancellation:
    """*canceller* fed with the reference lined up to each microphone block.

    Tuned by *config*'s ``threshold`` (the microphone level that starts an
    utterance) and ``echo_*`` fields; one left unset is read from `CFG`.
    """

    def __init__(
        self,
        canceller: AnyEchoCanceller,
        reference: EchoReference | None = None,
        config: DictationConfig | None = None,
    ) -> None:
        tuning = (config or DictationConfig()).resolve()
        self._tuning = tuning
        self._canceller = canceller
        self._threshold = tuning.threshold or 0.0
        self._leftovers: list[bool] = []  # per block of zrb speaking: loud?
        self._is_ready = False
        self._reference = reference or echo_reference
        # Enough played audio for the widest estimate (the window plus every
        # delay searched) of the oldest block the microphone's backlog holds.
        # An unbounded backlog cannot be covered; `can_cancel` tells.
        self._reference.ensure_seconds(
            _to_float(tuning.echo_delay_window)
            + _to_float(tuning.echo_max_delay)
            - _to_float(tuning.echo_min_delay)
            + _REFERENCE_MARGIN_SECONDS
            + max(0.0, _to_float(tuning.max_backlog))
        )
        self._np = _numpy()
        self._mic_history = self._np.zeros(
            int(RATE * _to_float(tuning.echo_delay_window)), self._np.float32
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

    def can_cancel(self, start_time: float) -> bool:
        """Whether zrb's voice can be cancelled out of a block captured from
        *start_time* on: it `is_ready`, and what zrb played then is still
        kept. A block read late (a backlog behind a slow transcription) may
        need audio the reference has already let go of."""
        if not self._canceller.needs_reference:
            return True
        if not self._is_ready or self._delay is None:
            return False
        return self._reference.is_covering(self._get_far_start(start_time))

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
            far = self._reference.read(self._get_far_start(start_time), len(mic))
        out = self._canceller.process(mic, far)
        self._judge_leftover(far, out)
        return out

    def _get_far_start(self, start_time: float) -> float:
        """When zrb played what a block captured from *start_time* on heard,
        led a little so the reference is never late."""
        return start_time - (self._delay or 0.0) + _to_float(self._tuning.echo_lead)

    def _judge_leftover(self, far: Any, out: Any) -> None:
        np = self._np
        tuning = self._tuning
        if self._is_ready or self._delay is None:
            return
        if float(np.sqrt(np.mean(far**2))) < _to_float(tuning.echo_playing_level):
            return  # zrb silent here: nothing to judge
        window = max(1, tuning.echo_ready_blocks or 0)
        self._leftovers = self._leftovers[
            max(0, len(self._leftovers) - window + 1) :
        ] + [float(np.sqrt(np.mean(out**2))) >= self._threshold]
        if (
            self._canceller.is_converged
            and len(self._leftovers) >= window
            and sum(self._leftovers) <= (tuning.echo_max_loud_leftovers or 0)
        ):
            self._is_ready = True

    def _remember(self, mic: Any, start_time: float) -> None:
        np = self._np
        self._mic_history = np.concatenate([self._mic_history[len(mic) :], mic])
        self._history_end = start_time + len(mic) / RATE
        self._since_estimate += len(mic) / RATE
        if self._since_estimate >= _to_float(self._tuning.echo_delay_interval):
            self._since_estimate = 0.0
            self._update_delay(self._estimate_delay())

    def _estimate_delay(self) -> float | None:
        """The delay at which the microphone best matches what was played
        (GCC-PHAT), or ``None`` without a clear answer."""
        np = self._np
        tuning = self._tuning
        min_delay = _to_float(tuning.echo_min_delay)
        max_delay = _to_float(tuning.echo_max_delay)
        mic = self._mic_history
        window_start = self._history_end - len(mic) / RATE
        # Reference covering every delay searched: played up to max_delay
        # before the window, or up to -min_delay after.
        far_start = window_start - max_delay
        far_length = len(mic) + int(RATE * (max_delay - min_delay))
        far = self._reference.read(far_start, far_length)
        if float(np.sqrt(np.mean(far**2))) < _to_float(tuning.echo_min_reference_level):
            return None
        size = 1 << int(np.ceil(np.log2(len(mic) + far_length)))
        cross = np.fft.rfft(mic, size) * np.conj(np.fft.rfft(far, size))
        correlation = np.fft.irfft(cross / (np.abs(cross) + 1e-12), size)
        # mic[t] matching far[t + offset]: offset = (_MAX - delay) * RATE.
        offsets = np.arange(0, int(RATE * (max_delay - min_delay)))
        values = correlation[(-offsets) % size]
        best = int(np.argmax(values))
        peak = float(values[best])
        typical = float(np.mean(np.abs(values))) + 1e-12
        if peak < _to_float(tuning.echo_min_peak) or peak / typical < _to_float(
            tuning.echo_min_peak_ratio
        ):
            return None
        return max_delay - offsets[best] / RATE

    def _update_delay(self, estimate: float | None) -> None:
        """Take *estimate* once a second one agrees with it. After that, only
        a delay that jumps (another output device) is taken, and starts the
        canceller over; drift is left to the canceller."""
        if estimate is None:
            return
        candidate, self._candidate = self._candidate, estimate
        if candidate is None or abs(candidate - estimate) > _to_float(
            self._tuning.echo_delay_agreement
        ):
            return
        if self._delay is None:
            self._delay = estimate
        elif abs(self._delay - estimate) > _to_float(self._tuning.echo_relock):
            self._canceller.reset()
            self._delay = estimate
            self._is_ready = False
            self._leftovers = []


def _to_float(value: float | None) -> float:
    return float(value or 0)


def _numpy() -> Any:
    # lazy: heavy third-party (numpy is a zrb[voice] extra); built only when
    # barge-in is on, which needs the microphone anyway.
    import numpy

    return numpy
