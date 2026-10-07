"""Cutting the microphone stream into utterances by loudness and silence.

`UtteranceCutter` is the pure part — blocks in, finished utterances out — so
it is testable without a microphone; `listen` feeds it from `sounddevice`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import closing
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, NamedTuple

from zrb.config.config import CFG
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.words import count_words
from zrb.llm.speech.player import is_speaking
from zrb.llm.util.teardown import close_quietly

if TYPE_CHECKING:
    # Annotation-only to avoid importing the backend barrel and its audio
    # dependencies into the capture module.
    from zrb.llm.dictation.backend.any_transcription_stream import (
        AnyTranscriptionStream,
    )

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # what the transcribers expect
# Window and minimum sample count for measuring zrb's voice level.
_ZRB_LEVEL_SECONDS = 3.0
_ZRB_LEVEL_MIN_SECONDS = 0.5
# Window and minimum sample count for measuring the room's noise floor.
_NOISE_FLOOR_SECONDS = 3.0
_NOISE_FLOOR_MIN_SECONDS = 0.5
# How often a push-to-talk recording checks whether to stop.
_RECORD_POLL_SECONDS = 0.1
# Retry count and delay for PortAudio's one-second ALSA startup deadline.
_OPEN_ATTEMPTS = 3
_OPEN_RETRY_SECONDS = 0.5


class Utterance(NamedTuple):
    """One utterance: 16-bit PCM, when its speech started and ended
    (`time.monotonic()`), whether it talked over zrb long enough to pause it
    (barge-in), the stream transcribing it, if any, and whether any of it
    was said over zrb's voice at all (a short "stop" is, without pausing;
    a barge-in always is)."""

    audio: bytes
    started_at: float
    ended_at: float
    is_barge_in: bool = False
    # Transcribing it since it started, when the backend streams.
    stream: "AnyTranscriptionStream | None" = None
    is_over_speech: bool = False


class MicState(Enum):
    """What the microphone is doing, as `listen` reports it."""

    LISTENING = "listening"
    HEARING = "hearing"  # speech in progress
    PAUSED = "paused"  # zrb is speaking, or just was


class UtteranceCutter:
    """Groups audio blocks into utterances.

    A block is loud when its level reaches ``threshold``, raised to
    ``noise_margin`` times the quietest the room was heard at over the last
    ``_NOISE_FLOOR_SECONDS``, so a conversation going on around the microphone
    does not open a turn of its own. That measure follows the room rather than
    the utterance: a room with no quiet moment in it is measured at its own
    level, which is what raises the bar over the noise, and a floor is never
    measured from the blocks zrb's own voice came back on. Speech starts at the
    first loud block, keeping ``pre_roll`` seconds from before it, and ends
    after ``silence`` quiet seconds (at least one block) or ``max_utterance`` in
    all (``0``: no limit). Speech shorter than ``min_speech``, from its first
    loud block to its last, is dropped as a cough or a click. While zrb is
    speaking, blocks are ignored. A negative duration counts as ``0``.

    With ``barge_in_enabled``, blocks captured while zrb speaks are heard
    too, against a higher bar: the
    microphone hears zrb's own voice there, so a block is loud only at
    ``barge_in_margin`` times the typical level zrb's voice reaches it (the
    median over its last few seconds, robust to the user talking over it
    for a moment, and not counting an utterance once it is a barge-in, when
    zrb is paused), and never below ``threshold``. Until that is measured the bar is ``barge_in_margin``
    times ``threshold``. It follows the volume and the room, and stays at
    ``threshold`` on headphones, where the microphone hears no zrb. An
    utterance with ``barge_in_min_speech`` of loud blocks over zrb
    `is_barge_in`; once `feed` or `flush` returns it, `is_finished_barge_in`
    says so, and `is_finished_over_speech` whether any of it was loud over
    zrb.
    """

    def __init__(self, config: DictationConfig) -> None:
        self._config = config
        self._block_seconds = get_block_seconds(config)
        self._pre_roll: deque[Any] = deque(maxlen=self._to_blocks(config.pre_roll))
        self._speech: list[Any] = []
        self._pre_roll_blocks = 0
        self._silent_blocks = 0
        self._started_at = 0.0
        self._is_barge_in_enabled = config.is_barge_in_enabled
        self._barge_in_blocks = max(1, self._to_blocks(config.barge_in_min_speech))
        self._loud_echo_blocks = 0
        self._is_finished_barge_in = False
        self._is_finished_over_speech = False
        self._utterance_count = 0
        self._zrb_levels: deque[float] = deque(
            maxlen=max(1, self._to_blocks(_ZRB_LEVEL_SECONDS))
        )
        self._zrb_level_blocks = max(1, self._to_blocks(_ZRB_LEVEL_MIN_SECONDS))
        # The room's background: the quiet blocks heard while zrb was silent,
        # which the bar under ordinary speech is measured from.
        self._background_levels: deque[float] = deque(
            maxlen=max(1, self._to_blocks(_NOISE_FLOOR_SECONDS))
        )
        self._noise_floor_blocks = max(1, self._to_blocks(_NOISE_FLOOR_MIN_SECONDS))
        self._utterance_bar = 0.0

    @property
    def is_barge_in_enabled(self) -> bool:
        """Whether blocks are heard while zrb speaks."""
        return self._is_barge_in_enabled

    @property
    def is_barge_in(self) -> bool:
        """Whether the utterance in progress has talked over zrb for long
        enough to interrupt it. False between utterances."""
        return self._loud_echo_blocks >= self._barge_in_blocks

    @property
    def is_finished_barge_in(self) -> bool:
        """Whether the utterance `feed` or `flush` last returned was a
        barge-in."""
        return self._is_finished_barge_in

    @property
    def is_finished_over_speech(self) -> bool:
        """Whether the utterance `feed` or `flush` last returned was loud
        over zrb's voice at all, even too briefly to be a barge-in."""
        return self._is_finished_over_speech

    def feed(
        self, block: Any, level: float, captured_at: float, is_echo: bool
    ) -> "tuple[list[Any], float, float] | None":
        """Add one block, captured by *captured_at*; return ``(blocks,
        started_at, ended_at)`` when it finishes an utterance. A block
        captured while zrb spoke (*is_echo*) is ignored with barge-in off,
        and held to the bar over zrb's voice with it on."""
        if is_echo and not self._is_barge_in_enabled:
            self.reset()
            return None
        is_over_zrb = self._is_over_zrb(is_echo)
        # An utterance keeps the bar it started with: the user's own voice,
        # measured as zrb's while they talk over it, must not cut them off.
        bar = self._utterance_bar if self._speech else self._get_bar(is_over_zrb)
        loud = level >= bar
        # Measure zrb's level only over it and the room's level only while silent;
        # after a barge-in, zrb is paused, so later blocks are the user's voice.
        if is_over_zrb and not self.is_barge_in:
            self._zrb_levels.append(level)
        if not is_over_zrb:
            self._background_levels.append(level)
        if not self._speech:
            if not loud:
                self._pre_roll.append(block)
                return None
            self._loud_echo_blocks = int(is_over_zrb)
            self._utterance_bar = bar
            self._utterance_count += 1
            self._speech = [*self._pre_roll, block]
            self._pre_roll_blocks = len(self._pre_roll)
            # The block's first sample, heard one block before it arrived.
            self._started_at = captured_at - self._block_seconds
            self._pre_roll.clear()
            return None
        return self._continue_speech(block, loud, captured_at, is_over_zrb)

    def _is_over_zrb(self, is_echo: bool) -> bool:
        """Whether a block may hold zrb's voice: captured while it spoke."""
        return is_echo

    def _get_bar(self, is_over_zrb: bool) -> float:
        """The bar a block must reach: over zrb, ``barge_in_margin`` times what
        its voice reaches the microphone; otherwise the room's own floor."""
        threshold = self._config.threshold or 0
        if not is_over_zrb:
            return max(threshold, self._get_noise_bar())
        margin = self._config.barge_in_margin or 1
        levels = sorted(self._zrb_levels)
        if len(levels) < self._zrb_level_blocks:
            return margin * threshold
        return max(threshold, margin * levels[len(levels) // 2])

    def _get_noise_bar(self) -> float:
        """The bar the room's background puts under ordinary speech:
        ``noise_margin`` times its quietest recent level, or ``0`` before
        enough of it has been heard and with ``noise_margin`` of 0 or less.

        The quietest block, not the typical one: a low estimate can only
        lower the bar, so the user's own speech in the window cannot cut off
        what they say next, where a median or a high percentile could. A block
        that heard nothing at all is not the room being quiet — a dropped
        buffer reads ``0`` — and is left out of the measure, since a single one
        would put the floor at ``0`` and hand the whole window back to
        ``threshold``."""
        margin = self._config.noise_margin or 0
        if margin <= 0:
            return 0.0
        heard = [level for level in self._background_levels if level > 0]
        if len(heard) < self._noise_floor_blocks:
            return 0.0
        return margin * min(heard)

    def _continue_speech(
        self, block: Any, loud: bool, captured_at: float, is_echo: bool
    ) -> "tuple[list[Any], float, float] | None":
        """Add *block* to the utterance in progress, returning it if the
        block ends it."""
        self._speech.append(block)
        self._silent_blocks = 0 if loud else self._silent_blocks + 1
        if loud and is_echo:
            self._loud_echo_blocks += 1
        config = self._config
        max_blocks = self._to_blocks(config.max_utterance)
        is_too_long = bool(max_blocks) and len(self._speech) >= max_blocks
        # At least one quiet block, or speech would end at its next block.
        silence_blocks = max(1, self._to_blocks(config.silence))
        if self._silent_blocks < silence_blocks and not is_too_long:
            return None
        return self._finish(captured_at)

    @property
    def is_hearing(self) -> bool:
        """Whether an utterance is in progress."""
        return bool(self._speech)

    @property
    def utterance_count(self) -> int:
        """How many utterances have started: tells the one in progress from
        the one before it."""
        return self._utterance_count

    @property
    def speech_blocks(self) -> list[Any]:
        """The blocks of the utterance in progress, pre-roll included."""
        return self._speech

    @property
    def quiet_seconds(self) -> float:
        """How long the utterance in progress has been quiet."""
        return self._silent_blocks * self._block_seconds

    def flush(self, ended_at: float) -> "tuple[list[Any], float, float] | None":
        """The utterance in progress, as `feed` would return it, if it holds
        enough speech; for a recording stopped mid-sentence."""
        return self._finish(ended_at)

    def _finish(self, ended_at: float) -> "tuple[list[Any], float, float] | None":
        """End the utterance in progress, returning it if it holds enough
        speech. Its barge-in status is kept for `is_finished_barge_in`
        before the reset clears it."""
        blocks, spoken_blocks = self._speech, self._count_spoken_blocks()
        is_barge_in = self.is_barge_in
        is_over_speech = self._loud_echo_blocks > 0
        self._is_finished_barge_in = False
        self._is_finished_over_speech = False
        self.reset()
        if not blocks or spoken_blocks < self._to_blocks(self._config.min_speech):
            return None
        self._is_finished_barge_in = is_barge_in
        self._is_finished_over_speech = is_over_speech
        return blocks, self._started_at, ended_at

    def _count_spoken_blocks(self) -> int:
        """From the first loud block to the last: pre-roll and trailing
        silence are not speech."""
        return len(self._speech) - self._pre_roll_blocks - self._silent_blocks

    def _to_blocks(self, seconds: float | None) -> int:
        return to_blocks(seconds, self._block_seconds)

    def reset(self) -> None:
        """Forget the utterance in progress, its barge-in count, and the
        pre-roll. The room's floor is kept: it describes the room, not the
        utterance, and clearing it would throw away what a loud room taught
        at the end of every utterance in it."""
        self._speech, self._silent_blocks = [], 0
        self._loud_echo_blocks = 0
        self._pre_roll.clear()


async def listen(
    config: DictationConfig,
    should_listen: Callable[[], bool],
    keep_partial: bool = False,
    on_state: Callable[[MicState], None] | None = None,
    on_barge_in: Callable[[], None] | None = None,
    create_stream: "CreateStream | None" = None,
    on_partial: Callable[[str], None] | None = None,
    on_barge_in_dropped: Callable[[], None] | None = None,
) -> AsyncGenerator[Utterance, None]:
    """Yield utterances from the default microphone while *should_listen*
    holds; the microphone closes once it stops holding. With *keep_partial*,
    speech cut off by that is yielded too. *on_state* is called with the
    `MicState` whenever it changes, starting with the first block.
    *on_barge_in* is called once per utterance, as soon as it has talked over
    zrb long enough to count as an interruption (`UtteranceCutter`), before
    the utterance ends.

    With *create_stream* returning a stream (`AnyTranscriptionStream`), each
    utterance is fed to one while it is spoken, handed over on its
    `Utterance.stream`, and *on_partial* sees the transcript so far. Such an
    utterance ends after ``min_silence`` quiet seconds, rather than
    ``silence``, once its transcript does not trail off on a word like "and".

    With barge-in on, blocks captured while zrb speaks are held to the bar
    over its voice (`UtteranceCutter`). *on_barge_in_dropped* is called when
    an utterance reported to *on_barge_in* ends without being yielded (too
    short to keep), so what it paused can resume.

    Audio keeps arriving while the caller handles an utterance (a slow
    transcription), and is kept, since the user may already be saying the
    next thing; but only the newest ``max_backlog`` seconds of it (``0``: no
    limit). When older audio is dropped, any utterance in progress is
    dropped with it rather than spliced across the gap.

    A caller that stops early must close this — `contextlib.aclosing` — or the
    microphone stays open until the generator is finalized.
    """
    np, sd = import_audio()
    loop = asyncio.get_running_loop()
    block_seconds = get_block_seconds(config)
    backlog = _Backlog(to_blocks(config.max_backlog, block_seconds))

    def on_audio(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        # Check at capture; queued blocks may be processed after zrb starts speaking.
        captured = _CapturedBlock(indata.copy(), is_speaking(), time.monotonic())
        loop.call_soon_threadsafe(backlog.append, captured)

    blocks = _BlockHandler(
        np,
        config,
        _BlockReports(on_state, on_barge_in, on_barge_in_dropped),
        _UtteranceStreamer(np, create_stream, on_partial),
    )
    stream = await _open_microphone(
        sd,
        on_audio,
        device=config.device or None,
        blocksize=int(SAMPLE_RATE * block_seconds),
    )
    try:
        with closing(stream):
            while should_listen():
                item = await backlog.get(timeout=block_seconds * 5)
                if item is None:
                    continue
                utterance = await blocks.handle(item)
                if utterance is not None:
                    yield utterance
        if keep_partial:
            utterance = await blocks.flush(time.monotonic())
            if utterance is not None:
                yield utterance
    finally:
        await blocks.close()


CreateStream = Callable[[], Awaitable["AnyTranscriptionStream | None"]]


@dataclass(frozen=True)
class _CapturedBlock:
    """One microphone block, captured by *captured_at*, while zrb was
    speaking (*is_echo*) or not. A block *follows_gap* when older blocks
    before it were dropped."""

    block: Any
    is_echo: bool
    captured_at: float
    follows_gap: bool = False


class _BlockHandler:
    """Runs each captured block through the `UtteranceCutter`, reports the
    microphone's state and a barge-in, and feeds the utterance's stream."""

    def __init__(
        self,
        np: Any,
        config: DictationConfig,
        reports: "_BlockReports",
        streamer: "_UtteranceStreamer",
    ) -> None:
        self._np = np
        self._config = config
        self._cutter = UtteranceCutter(config)
        self._reports = reports
        self._streamer = streamer

    async def handle(self, captured: _CapturedBlock) -> Utterance | None:
        cutter = self._cutter
        if captured.follows_gap:
            cutter.reset()
        block = captured.block
        # Ignore zrb's voice when barge-in is off; use a higher bar when it is on.
        is_deaf = captured.is_echo and not cutter.is_barge_in_enabled
        level = float(self._np.sqrt(self._np.mean(block**2)))
        finished = cutter.feed(block, level, captured.captured_at, captured.is_echo)
        if finished is None:
            finished = await self._continue(captured.captured_at, is_deaf)
        if finished is None:
            return None
        return await self._to_utterance(finished, is_deaf)

    async def _continue(
        self, captured_at: float, is_deaf: bool
    ) -> "tuple[list[Any], float, float] | None":
        """After a block that did not finish an utterance: report it, stream
        it, and end the utterance early if it sounds finished."""
        cutter = self._cutter
        self._reports.update(cutter, is_deaf)
        await self._streamer.update(cutter)
        if not self._streamer.should_end(cutter, self._config):
            return None
        finished = cutter.flush(captured_at)
        if finished is None:
            # A reported barge-in is dropped with an utterance too short to keep.
            self._reports.update(cutter, is_deaf)
        return finished

    async def flush(self, ended_at: float) -> Utterance | None:
        """The utterance in progress, for a recording stopped mid-sentence."""
        finished = self._cutter.flush(ended_at)
        if finished is None:
            return None
        return await self._to_utterance(finished, is_deaf=False)

    async def close(self) -> None:
        """The microphone is closing: an utterance still in progress is
        dropped, and so is a barge-in it reported, so what it paused
        resumes."""
        self._reports.abandon()
        await self._streamer.abandon()

    async def _to_utterance(
        self, finished: "tuple[list[Any], float, float]", is_deaf: bool
    ) -> Utterance:
        """The finished utterance, handed to the caller. A barge-in it
        reported goes with it, never reported dropped: the caller settles it
        once the transcript says whether it was words."""
        self._reports.hand_over()
        self._reports.update(self._cutter, is_deaf)
        stream = await self._streamer.take(finished[0])
        cutter = self._cutter
        return _to_utterance(
            self._np,
            finished,
            cutter.is_finished_barge_in,
            stream,
            cutter.is_finished_over_speech,
        )


class _BlockReports:
    """Tells the caller what the microphone is doing (`MicState`), that an
    utterance talked over zrb, and that one reported so was dropped."""

    def __init__(
        self,
        on_state: Callable[[MicState], None] | None,
        on_barge_in: Callable[[], None] | None,
        on_barge_in_dropped: Callable[[], None] | None,
    ) -> None:
        self._on_state = on_state
        self._on_barge_in = on_barge_in
        self._on_barge_in_dropped = on_barge_in_dropped
        self._state: MicState | None = None
        self._is_barge_in_reported = False

    def abandon(self) -> None:
        """Report a barge-in still in progress as dropped."""
        if self._is_barge_in_reported:
            self._is_barge_in_reported = False
            _call(self._on_barge_in_dropped)

    def hand_over(self) -> None:
        """The utterance in progress is being yielded: a barge-in it
        reported is the caller's to settle now, not dropped."""
        self._is_barge_in_reported = False

    def update(self, cutter: UtteranceCutter, is_deaf: bool) -> None:
        """After a block, deaf to zrb's voice (*is_deaf*) or not. An
        utterance that stops being heard without being handed over (too
        short, or cut by zrb's voice) drops its barge-in."""
        if cutter.is_barge_in and not self._is_barge_in_reported:
            self._is_barge_in_reported = True
            _call(self._on_barge_in)
        if not cutter.is_hearing and self._is_barge_in_reported:
            self._is_barge_in_reported = False
            _call(self._on_barge_in_dropped)
        state = _get_mic_state(cutter, is_deaf)
        if self._on_state is not None and state != self._state:
            self._on_state(state)
        self._state = state


def _call(callback: Callable[[], None] | None) -> None:
    if callback is not None:
        callback()


class _UtteranceStreamer:
    """Feeds the utterance in progress to a transcription stream, block by
    block, so its transcript is mostly done when it ends. A stream that
    fails is given up on, for this and every later utterance: they are then
    transcribed whole once they end, as a backend without streams does."""

    def __init__(
        self,
        np: Any,
        create_stream: "CreateStream | None",
        on_partial: Callable[[str], None] | None,
    ) -> None:
        self._np = np
        self._create_stream = create_stream
        self._on_partial = on_partial
        self._stream: "AnyTranscriptionStream | None" = None
        self._fed = 0
        # `UtteranceCutter.utterance_count` of the utterance being fed.
        self._utterance = 0

    async def update(self, cutter: UtteranceCutter) -> None:
        """Feed the blocks the utterance gained; abandon a dropped one, or
        one a new utterance replaced (after a gap) before it ended."""
        blocks = cutter.speech_blocks
        if not blocks or cutter.utterance_count != self._utterance:
            await self.abandon()
        if not blocks or self._create_stream is None:
            return
        self._utterance = cutter.utterance_count
        try:
            await self._stream_blocks(blocks)
        except Exception as exc:
            await self._give_up(exc)

    async def _stream_blocks(self, blocks: list[Any]) -> None:
        if self._create_stream is None:
            return
        if self._stream is None:
            self._stream = await self._create_stream()
            if self._stream is None:
                # Batch-only backend; do not request another stream.
                self._create_stream = None
                return
        await self._feed(blocks)
        if self._on_partial is not None:
            self._on_partial(self._stream.partial)

    def should_end(self, cutter: UtteranceCutter, config: DictationConfig) -> bool:
        """Whether the utterance sounds finished after a short pause."""
        min_silence = config.min_silence or 0
        if self._stream is None or min_silence <= 0 or not cutter.is_hearing:
            return False
        if cutter.quiet_seconds < min_silence:
            return False
        return count_words(self._stream.partial) > 0

    async def take(self, blocks: list[Any]) -> "AnyTranscriptionStream | None":
        """Hand over the stream of an utterance that ended with *blocks*."""
        stream = self._stream
        if stream is not None:
            try:
                await self._feed(blocks)
            except Exception as exc:
                await self._give_up(exc)
                return None
        self._stream, self._fed = None, 0
        return stream

    async def abandon(self) -> None:
        stream, self._stream, self._fed = self._stream, None, 0
        if stream is not None:
            await stream.close()

    async def _give_up(self, exc: Exception) -> None:
        logger.warning(
            f"Streaming transcription failed ({exc}); utterances are "
            "transcribed once they end instead"
        )
        self._create_stream = None
        try:
            await self.abandon()
        except Exception as close_exc:
            logger.warning(f"Closing a transcription stream failed: {close_exc}")

    async def _feed(self, blocks: list[Any]) -> None:
        new_blocks, self._fed = blocks[self._fed :], len(blocks)
        if new_blocks and self._stream is not None:
            await self._stream.feed(_to_pcm(self._np, new_blocks))


def _get_mic_state(cutter: UtteranceCutter, is_deaf: bool) -> MicState:
    if is_deaf:
        return MicState.PAUSED
    return MicState.HEARING if cutter.is_hearing else MicState.LISTENING


class _Backlog:
    """Captured blocks waiting to be read, at most *max_blocks* of them
    (``0``: no limit). When the oldest is dropped, the block now first is
    marked as following a gap, so the reader never joins audio across it.

    Touched only from the event loop's thread: the audio callback hands
    blocks over with `call_soon_threadsafe`.
    """

    def __init__(self, max_blocks: int) -> None:
        self._max_blocks = max_blocks
        self._blocks: deque[_CapturedBlock] = deque()
        self._arrived = asyncio.Event()

    def append(self, captured: _CapturedBlock) -> None:
        if self._max_blocks and len(self._blocks) >= self._max_blocks:
            self._blocks.popleft()
            if self._blocks:
                self._blocks[0] = replace(self._blocks[0], follows_gap=True)
            else:
                captured = replace(captured, follows_gap=True)
        self._blocks.append(captured)
        self._arrived.set()

    async def get(self, timeout: float) -> _CapturedBlock | None:
        """The oldest block, or ``None`` if none arrives within *timeout*."""
        while not self._blocks:
            self._arrived.clear()
            try:
                await asyncio.wait_for(self._arrived.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
        return self._blocks.popleft()


def _to_utterance(
    np: Any,
    finished: "tuple[list[Any], float, float]",
    is_barge_in: bool = False,
    stream: "AnyTranscriptionStream | None" = None,
    is_over_speech: bool = False,
) -> Utterance:
    speech, started_at, ended_at = finished
    return Utterance(
        _to_pcm(np, speech),
        started_at,
        ended_at,
        is_barge_in,
        stream,
        is_over_speech or is_barge_in,
    )


def _to_pcm(np: Any, blocks: list[Any]) -> bytes:
    return (np.concatenate(blocks, axis=0) * 32767).astype(np.int16).tobytes()


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


def to_device(device: "str | int | None") -> "int | str | None":
    """A device setting as `sounddevice` takes it: a digit string is an index.

    `sounddevice` reads an `int` as a device index and a `str` as a name to
    match, so "2" has to become ``2``. A non-numeric value passes through as a
    name, and empty or unset is PortAudio's own default.
    """
    if device is None or isinstance(device, int):
        return device
    text = device.strip()
    if not text:
        return None
    return int(text) if text.isdigit() else text


async def _open_microphone(
    sd: Any,
    on_audio: Callable[..., None],
    device: "str | int | None" = None,
    **options: Any,
) -> Any:
    """The microphone, open and running, or a `RuntimeError` saying why.

    PortAudio gives the ALSA thread it starts one second to come up and reports
    ``paTimedOut`` when it misses: a WSL2 VM stalling on I/O misses it, for
    reasons that have nothing to do with zrb, and the stall is over by the time
    the call returns. So a start that fails is tried again, and only the last
    failure is raised. A stream that never started is closed first, best-effort,
    so the next try does not contend with it for the device.

    A failure to construct the stream (no such device, PortAudio missing) is
    not retried.
    """
    device = to_device(device)
    attempt = 0
    while True:
        attempt += 1
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=on_audio,
                device=device,
                **options,
            )
        except Exception as e:
            raise RuntimeError(
                f"Cannot open microphone: {e}. Check permissions and that no "
                "other app is using the mic."
            ) from e
        try:
            stream.start()
            return stream
        except Exception as e:
            await close_quietly(stream.close, "the microphone that would not start")
            if attempt >= _OPEN_ATTEMPTS:
                raise RuntimeError(_microphone_failure_message(device, e)) from e
            logger.warning(f"Starting the microphone failed ({e}); trying again")
            await asyncio.sleep(_OPEN_RETRY_SECONDS)


def _microphone_failure_message(device: "int | str | None", error: Exception) -> str:
    """What to say when the microphone will not start.

    Names the device PortAudio was asked for — ``None`` is its own default, what
    ``sd.default.device`` resolves to — and the setting that names another,
    because which device a Linux or WSL machine opens is the usual difference
    between a microphone that works and one that does not.
    """
    return (
        f"Cannot open microphone: {error}. PortAudio was asked for device "
        f"{device!r} (None: its own default). Check permissions and that no other "
        f"app is using the mic, and set {CFG.ENV_PREFIX}_LLM_DICTATION_DEVICE to "
        "name another one."
    )


def get_block_seconds(config: DictationConfig) -> float:
    """``config.block_duration``, the seconds in each microphone block;
    unset, `CFG.LLM_DICTATION_BLOCK_DURATION`."""
    seconds = config.block_duration
    if seconds is None:
        seconds = CFG.LLM_DICTATION_BLOCK_DURATION
    if seconds is None or seconds <= 0:
        raise ValueError(
            f"block_duration must be a positive number of seconds, got {seconds!r}; "
            "set ZRB_LLM_DICTATION_BLOCK_DURATION (default 0.1)."
        )
    return seconds


def to_blocks(seconds: float | None, block_seconds: float) -> int:
    """*seconds* as whole blocks of *block_seconds*; none or negative is 0."""
    return max(0, round((seconds or 0) / block_seconds))


async def record(should_record: Callable[[], bool]) -> bytes:
    """Everything the default microphone hears while *should_record* holds,
    as 16-bit PCM, pauses included; for a button held down to talk."""
    np, sd = import_audio()
    loop = asyncio.get_running_loop()
    blocks: "asyncio.Queue[Any]" = asyncio.Queue()

    def on_audio(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        loop.call_soon_threadsafe(blocks.put_nowait, indata.copy())

    recorded: list[Any] = []
    with closing(await _open_microphone(sd, on_audio)):
        while should_record():
            try:
                recorded.append(
                    await asyncio.wait_for(blocks.get(), _RECORD_POLL_SECONDS)
                )
            except asyncio.TimeoutError:
                continue
    if not recorded:
        return b""
    return (np.concatenate(recorded, axis=0) * 32767).astype(np.int16).tobytes()
