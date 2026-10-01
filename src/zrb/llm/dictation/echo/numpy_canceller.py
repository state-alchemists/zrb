"""An acoustic echo canceller in pure NumPy.

A partitioned-block frequency-domain adaptive filter (PBFDAF, the "MDF"
algorithm Speex uses) learns how zrb's voice travels from the speakers to
the microphone and subtracts its prediction; a residual echo suppressor
then damps what the filter missed. NumPy is already a dictation dependency,
so it runs wherever dictation does, Termux included.

Measured on a simulated laptop (speaker delay and distortion, room reverb,
mic noise): once converged it removes about 30 dB of echo at normal volume,
23 dB loud, 15 dB when the speakers distort, and vosk hears no words in what
is left. It needs a few seconds of zrb speaking to converge, once a session.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller

RATE = 16000


class NumpyEchoCanceller(AnyEchoCanceller):
    """Tuned by *config*'s ``echo_frame`` (seconds per filter step),
    ``echo_filter_length`` (seconds of echo path covered: playback delay
    plus the room's tail), ``echo_step``, ``echo_suppress_residual`` and
    ``echo_converge_after``; one left unset is read from `CFG`."""

    def __init__(self, config: DictationConfig | None = None) -> None:
        tuning = (config or DictationConfig()).resolve()
        block = max(1, int(round(RATE * (tuning.echo_frame or 0))))
        self._options = (
            block,
            (tuning.echo_filter_length or 0) * 1000,
            tuning.echo_step or 0.0,
            bool(tuning.echo_suppress_residual),
        )
        self._converged_after = tuning.echo_converge_after or 0.0
        self._start(*self._options)

    def reset(self) -> None:
        self._start(*self._options)

    def _start(self, block: int, filter_ms: float, step: float, suppress: bool) -> None:
        np = _numpy()
        self._np = np
        self._n = block
        parts = max(1, int(np.ceil(RATE * filter_ms / 1000 / block)))
        bins = block + 1
        self._weights = np.zeros((parts, bins), np.complex128)
        self._far_spectra = np.zeros((parts, bins), np.complex128)
        self._far_previous = np.zeros(block)
        self._power = np.full(bins, 1e-6)
        self._step = step
        self._suppress = suppress
        self._window = np.sqrt(np.hanning(2 * block + 1)[:-1])
        self._error_previous = np.zeros(block)
        self._echo_previous = np.zeros(block)
        self._overlap = np.zeros(block)
        self._echo_energy = 1e-9
        self._error_energy = 1e-9
        self._far_energy = 0.0
        # Blocks in and out: `process` takes and returns any length.
        self._mic_pending = np.zeros(0)
        self._far_pending = np.zeros(0)
        # Primed with one block of silence: the suppressor's overlap-add
        # delays its output by a block.
        self._out_pending = np.zeros(block if suppress else 0)
        self._far_active_samples = 0

    @property
    def name(self) -> str:
        return "numpy"

    @property
    def is_converged(self) -> bool:
        """Once it has adapted over a couple of seconds of zrb speaking.
        Whether that removed enough is judged by `EchoCancellation`, from
        what is left."""
        return self._far_active_samples >= RATE * self._converged_after

    def process(self, mic: Any, far: Any) -> Any:
        np = self._np
        n = self._n
        self._mic_pending = np.concatenate([self._mic_pending, mic])
        self._far_pending = np.concatenate([self._far_pending, far])
        outputs = [self._out_pending]
        while len(self._mic_pending) >= n:
            mic_block, self._mic_pending = self._mic_pending[:n], self._mic_pending[n:]
            far_block, self._far_pending = self._far_pending[:n], self._far_pending[n:]
            outputs.append(self._process_block(mic_block, far_block))
        out = np.concatenate(outputs)
        self._out_pending = out[len(mic) :]
        return out[: len(mic)].astype(np.float32)

    def _process_block(self, mic: Any, far: Any) -> Any:
        np = self._np
        n = self._n
        self._far_spectra = np.roll(self._far_spectra, 1, axis=0)
        self._far_spectra[0] = np.fft.rfft(np.concatenate([self._far_previous, far]))
        self._far_previous = far
        echo = np.fft.irfft(np.sum(self._weights * self._far_spectra, axis=0))[n:]
        error = mic - echo
        far_energy = float(np.dot(far, far))
        self._far_energy = 0.9 * self._far_energy + 0.1 * far_energy
        if self._far_energy > 1e-6:
            self._adapt(mic, echo, error)
            if far_energy > 1e-6:
                self._far_active_samples += len(mic)
        if not self._suppress:
            return error
        return self._suppress_residual(error, echo)

    def _adapt(self, mic: Any, echo: Any, error: Any) -> None:
        """One normalized gradient step, slowed when something other than
        echo (the user) dominates, so talking over zrb does not unlearn the
        room."""
        np = self._np
        n = self._n
        self._echo_energy = 0.9 * self._echo_energy + 0.1 * float(np.dot(echo, echo))
        self._error_energy = 0.9 * self._error_energy + 0.1 * float(
            np.dot(error, error)
        )
        is_diverged = float(np.dot(error, error)) > float(np.dot(mic, mic))
        is_echo_dominant = self._error_energy < 4 * self._echo_energy
        step = self._step if is_echo_dominant or is_diverged else self._step * 0.05
        error_spectrum = np.fft.rfft(np.concatenate([np.zeros(n), error]))
        # Normalized by the far-end power over the whole filter length; the
        # floor keeps bins with almost no energy (pauses between words) from
        # taking huge steps.
        far_power = np.sum(np.abs(self._far_spectra) ** 2, axis=0)
        self._power = 0.7 * self._power + 0.3 * far_power
        floor = 1e-2 * float(np.mean(self._power)) + 1e-4
        self._weights += (
            step * np.conj(self._far_spectra) * error_spectrum / (self._power + floor)
        )
        # Gradient constraint: keep each partition a filter of n taps.
        taps = np.fft.irfft(self._weights, axis=1)
        taps[:, n:] = 0
        self._weights = np.fft.rfft(taps, axis=1)

    def _suppress_residual(self, error: Any, echo: Any) -> Any:
        """Damp the frequencies where the echo estimate is large next to
        what is left (a Wiener-like gain), windowed and overlap-added."""
        np = self._np
        n = self._n
        error_frame = np.concatenate([self._error_previous, error]) * self._window
        echo_frame = np.concatenate([self._echo_previous, echo]) * self._window
        self._error_previous, self._echo_previous = error, echo
        error_spectrum = np.fft.rfft(error_frame)
        echo_power = np.abs(np.fft.rfft(echo_frame)) ** 2
        error_power = np.abs(error_spectrum) ** 2
        gain = np.clip(
            1 - 2.0 * echo_power / (error_power + echo_power + 1e-12), 0.05, 1
        )
        frame = np.fft.irfft(error_spectrum * gain) * self._window
        out = frame[:n] + self._overlap
        self._overlap = frame[n:]
        return out


def _numpy() -> Any:
    # lazy: heavy third-party (numpy is a zrb[voice] extra); a canceller is
    # built only when barge-in is on, which needs the microphone anyway.
    import numpy

    return numpy
