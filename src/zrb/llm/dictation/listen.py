"""Cutting the microphone stream into utterances by loudness and silence.

`UtteranceCutter` is the pure part — blocks in, finished utterances out — so
it is testable without a microphone; `listen` feeds it from `sounddevice`.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import Any, NamedTuple

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.speech.player import is_speaking

SAMPLE_RATE = 16000  # what the transcribers expect
BLOCK_SECONDS = 0.1


class Utterance(NamedTuple):
    """One utterance: 16-bit PCM, and when it started and ended
    (`time.monotonic()` at capture)."""

    audio: bytes
    started_at: float
    ended_at: float


class UtteranceCutter:
    """Groups audio blocks into utterances.

    A block is loud when its level reaches ``threshold``. Speech starts at the
    first loud block, keeping ``pre_roll`` seconds from before it, and ends
    after ``silence`` quiet seconds or ``max_utterance`` in all. Speech
    shorter than ``min_speech``, from its first loud block to its last, is
    dropped as a cough or a click. While zrb is
    speaking, and for ``echo_cooldown`` after, blocks are ignored.
    """

    def __init__(self, config: DictationConfig) -> None:
        self._config = config
        self._pre_roll: deque[Any] = deque(
            maxlen=max(1, _to_blocks(config.pre_roll or 0))
        )
        self._speech: list[Any] = []
        self._pre_roll_blocks = 0
        self._silent_blocks = 0
        self._started_at = 0.0
        self._cooldown_blocks = 0

    def feed(
        self, block: Any, level: float, captured_at: float, is_echo: bool
    ) -> "tuple[list[Any], float, float] | None":
        """Add one block; return ``(blocks, started_at, ended_at)`` when it
        finishes an utterance."""
        if is_echo:
            self._reset()
            self._cooldown_blocks = _to_blocks(self._config.echo_cooldown or 0)
            return None
        if self._cooldown_blocks:
            self._cooldown_blocks -= 1
            return None
        loud = level >= (self._config.threshold or 0)
        if not self._speech:
            self._pre_roll.append(block)
            if loud:
                self._speech = list(self._pre_roll)
                self._pre_roll_blocks = len(self._speech) - 1
                self._started_at = captured_at
                self._pre_roll.clear()
            return None
        self._speech.append(block)
        self._silent_blocks = 0 if loud else self._silent_blocks + 1
        config = self._config
        if self._silent_blocks < _to_blocks(config.silence or 0) and len(
            self._speech
        ) < _to_blocks(config.max_utterance or 0):
            return None
        blocks, spoken_blocks = self._speech, self._count_spoken_blocks()
        self._reset()
        if spoken_blocks < _to_blocks(config.min_speech or 0):
            return None
        return blocks, self._started_at, captured_at

    def flush(self, ended_at: float) -> "tuple[list[Any], float, float] | None":
        """The utterance in progress, as `feed` would return it, if it holds
        enough speech; for a recording stopped mid-sentence."""
        blocks, spoken_blocks = self._speech, self._count_spoken_blocks()
        self._reset()
        if not blocks or spoken_blocks < _to_blocks(self._config.min_speech or 0):
            return None
        return blocks, self._started_at, ended_at

    def _count_spoken_blocks(self) -> int:
        """From the first loud block to the last: pre-roll and trailing
        silence are not speech."""
        return len(self._speech) - self._pre_roll_blocks - self._silent_blocks

    def _reset(self) -> None:
        self._speech, self._silent_blocks = [], 0
        self._pre_roll.clear()


async def listen(
    config: DictationConfig,
    should_listen: Callable[[], bool],
    keep_partial: bool = False,
) -> AsyncIterator[Utterance]:
    """Yield utterances from the default microphone while *should_listen*
    holds; the microphone closes once it stops holding. With *keep_partial*,
    speech cut off by that is yielded too."""
    np, sd = import_audio()
    loop = asyncio.get_running_loop()
    blocks: "asyncio.Queue[tuple[Any, bool, float]]" = asyncio.Queue()

    def on_audio(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        # Checked at capture: blocks queue up during transcription, so
        # checking later would let zrb's own voice through.
        captured = (indata.copy(), is_speaking(), time.monotonic())
        loop.call_soon_threadsafe(blocks.put_nowait, captured)

    cutter = UtteranceCutter(config)
    stream = _open_microphone(sd, on_audio, blocksize=int(SAMPLE_RATE * BLOCK_SECONDS))
    with stream:
        while should_listen():
            try:
                block, is_echo, captured_at = await asyncio.wait_for(
                    blocks.get(), timeout=BLOCK_SECONDS * 5
                )
            except asyncio.TimeoutError:
                continue
            level = float(np.sqrt(np.mean(block**2)))
            finished = cutter.feed(block, level, captured_at, is_echo)
            if finished is not None:
                yield _to_utterance(np, finished)
    if keep_partial:
        finished = cutter.flush(time.monotonic())
        if finished is not None:
            yield _to_utterance(np, finished)


def _to_utterance(np: Any, finished: "tuple[list[Any], float, float]") -> Utterance:
    speech, started_at, ended_at = finished
    audio = (np.concatenate(speech, axis=0) * 32767).astype(np.int16)
    return Utterance(audio.tobytes(), started_at, ended_at)


def import_audio() -> tuple[Any, Any]:
    """numpy and sounddevice, or a `RuntimeError` saying how to install them."""
    try:
        # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
        import numpy as np
        import sounddevice as sd
    except (ImportError, OSError) as e:
        raise RuntimeError(
            f"Dictation needs the zrb[voice] extra ({e}): pip install 'zrb[voice]'"
        ) from e
    return np, sd


def _open_microphone(sd: Any, on_audio: Callable[..., None], **options: Any) -> Any:
    try:
        return sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=on_audio,
            **options,
        )
    except Exception as e:
        raise RuntimeError(
            f"Cannot open microphone: {e}. Check permissions and that no "
            "other app is using the mic."
        ) from e


def _to_blocks(seconds: float) -> int:
    return round(seconds / BLOCK_SECONDS)


async def record(should_record: Callable[[], bool]) -> bytes:
    """Everything the default microphone hears while *should_record* holds,
    as 16-bit PCM, pauses included; for a button held down to talk."""
    np, sd = import_audio()
    loop = asyncio.get_running_loop()
    blocks: "asyncio.Queue[Any]" = asyncio.Queue()

    def on_audio(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        loop.call_soon_threadsafe(blocks.put_nowait, indata.copy())

    recorded: list[Any] = []
    with _open_microphone(sd, on_audio):
        while should_record():
            try:
                recorded.append(await asyncio.wait_for(blocks.get(), BLOCK_SECONDS))
            except asyncio.TimeoutError:
                continue
    if not recorded:
        return b""
    return (np.concatenate(recorded, axis=0) * 32767).astype(np.int16).tobytes()
