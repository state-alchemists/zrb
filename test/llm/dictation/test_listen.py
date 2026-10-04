"""Tests for `zrb.llm.dictation.listen`.

The microphone is a fake `sounddevice` whose `InputStream` hands its callback
to the test, which then plays blocks into it. Opening that microphone, and
recording from it, are `test_listen_microphone.py`'s.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import MicState, UtteranceCutter, listen

np = pytest.importorskip("numpy")


class FakeStream:
    """A `sounddevice.InputStream`: started by `_open_microphone`, closed when
    the listening stops."""

    def __init__(self):
        self.is_started = False
        self.is_closed = False

    def start(self):
        self.is_started = True

    def close(self):
        self.is_closed = True


def _fake_sounddevice(captured):
    def make_stream(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = make_stream
    return fake_sd


def _holds_for(checks):
    """A should_record/should_listen that holds for *checks* calls."""
    remaining = [checks]

    def should_continue():
        remaining[0] -= 1
        return remaining[0] >= 0

    return should_continue


def _block(value):
    return np.full((2, 1), value, dtype=np.float32)


def _pcm(*values):
    return (np.array(values, dtype=np.float32) * 32767).astype(np.int16).tobytes()


async def _play(captured, blocks):
    await asyncio.sleep(0)  # let the coroutine open the stream
    for block in blocks:
        captured["callback"](block, len(block), None, None)


# --- listen -----------------------------------------------------------------


def _listen_config():
    # 0.1 s blocks: speech starts at a loud block and ends after 2 quiet ones.
    return DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0.1,
    )


async def _collect(
    blocks, keep_partial=False, speaking=False, on_state=None, on_captured=None
):
    captured = {}

    async def consume():
        should_listen = _holds_for(len(blocks))
        stream = listen(
            _listen_config(),
            should_listen,
            keep_partial=keep_partial,
            on_state=on_state,
            on_captured=on_captured,
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=speaking),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        return await task, captured


@pytest.mark.asyncio
async def test_listen_yields_an_utterance_ended_by_silence():
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, captured = await _collect(blocks)

    assert len(utterances) == 1
    # pre_roll=0.1 keeps the one quiet block before speech started.
    assert utterances[0].audio == _pcm(*[0.0] * 2, *[0.5] * 4, *[0.0] * 4)
    assert utterances[0].started_at <= utterances[0].ended_at
    assert captured["blocksize"] == 1600


@pytest.mark.asyncio
async def test_listen_drops_speech_cut_off_by_stop_without_keep_partial():
    utterances, _ = await _collect([_block(0.5), _block(0.5)])

    assert utterances == []


@pytest.mark.asyncio
async def test_listen_keep_partial_yields_speech_cut_off_by_stop():
    utterances, _ = await _collect([_block(0.5), _block(0.5)], keep_partial=True)

    assert [u.audio for u in utterances] == [_pcm(*[0.5] * 4)]


@pytest.mark.asyncio
async def test_listen_hands_every_captured_block_to_on_captured():
    """The capture is handed over as it is captured, before it is cut.

    This is the hand-off the Pipecat pipeline is fed from (ADR-0107, stage 1):
    every block, the pre-roll and the trailing silence included, as 16 kHz mono
    16-bit PCM — what `push_audio` takes.
    """
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]
    seen: list[bytes] = []

    async def on_captured(pcm: bytes) -> None:
        seen.append(pcm)

    utterances, _ = await _collect(blocks, on_captured=on_captured)

    assert len(utterances) == 1
    assert seen == [_pcm(*[value] * 2) for value in (0.0, 0.5, 0.5, 0.0, 0.0)]


@pytest.mark.asyncio
async def test_listen_ignores_blocks_captured_while_zrb_speaks():
    blocks = [_block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, _ = await _collect(blocks, keep_partial=True, speaking=True)

    assert utterances == []


# --- UtteranceCutter --------------------------------------------------------


@pytest.mark.asyncio
async def test_listen_reports_each_change_of_mic_state():
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]
    states = []

    await _collect(blocks, on_state=states.append)

    assert states == [MicState.LISTENING, MicState.HEARING, MicState.LISTENING]


@pytest.mark.asyncio
async def test_listen_reports_the_mic_paused_while_zrb_speaks():
    states = []

    await _collect([_block(0.5), _block(0.5)], speaking=True, on_state=states.append)

    assert states == [MicState.PAUSED]


def _cutter(**config):
    from zrb.llm.dictation.listen import UtteranceCutter

    fields = dict(
        threshold=0.1,
        silence=0.2,
        min_speech=0.2,
        max_utterance=1.0,
        pre_roll=0.2,
    )
    return UtteranceCutter(DictationConfig(**{**fields, **config}).resolve())


def _feed(cutter, levels, echo_at=()):
    """Feed one block per level (block i captured at i/10 s, so its speech
    began at (i-1)/10 s); the finished utterances as (blocks, started_at,
    ended_at), times rounded."""
    finished = []
    for index, level in enumerate(levels):
        done = cutter.feed(index, level, index / 10, index in echo_at)
        if done is not None:
            blocks, started_at, ended_at = done
            finished.append((blocks, round(started_at, 6), round(ended_at, 6)))
    return finished


def test_speech_ends_after_the_silence_and_keeps_its_pre_roll():
    # pre_roll=0.2 keeps the two quiet blocks before the first loud one.
    finished = _feed(_cutter(), [0, 0, 0, 1, 1, 1, 0, 0, 0])

    assert finished == [([1, 2, 3, 4, 5, 6, 7], 0.2, 0.7)]


def test_zero_pre_roll_keeps_no_quiet_block():
    finished = _feed(_cutter(pre_roll=0), [0, 0, 1, 1, 0, 0])

    assert finished == [([2, 3, 4, 5], 0.1, 0.5)]


def test_zero_max_utterance_means_no_limit():
    finished = _feed(_cutter(max_utterance=0), [1] * 30 + [0, 0])

    assert len(finished) == 1
    assert len(finished[0][0]) == 32  # 30 loud and 2 quiet; nothing came before


def test_negative_pre_roll_keeps_no_quiet_block():
    finished = _feed(_cutter(pre_roll=-1), [0, 0, 1, 1, 0, 0])

    assert finished == [([2, 3, 4, 5], 0.1, 0.5)]


def test_negative_max_utterance_means_no_limit():
    finished = _feed(_cutter(max_utterance=-1), [1] * 30 + [0, 0])

    assert len(finished) == 1
    assert len(finished[0][0]) == 32


def test_zero_silence_ends_speech_at_the_first_quiet_block():
    finished = _feed(_cutter(silence=0, pre_roll=0), [1, 1, 0, 1, 1, 0])

    assert finished == [([0, 1, 2], -0.1, 0.2), ([3, 4, 5], 0.2, 0.5)]


def test_a_click_shorter_than_min_speech_is_dropped():
    assert _feed(_cutter(), [0, 1, 0, 0, 0]) == []


def test_speech_is_cut_at_max_utterance():
    (blocks, _, _), *_ = _feed(_cutter(max_utterance=0.5), [1] * 12)

    assert len(blocks) == 5


def test_blocks_while_zrb_speaks_are_ignored():
    levels = [1, 1, 1, 1, 0, 0, 0]
    # Echo on block 1 discards the speech so far; what follows is heard at
    # once, since nothing is held back after zrb stops any more.
    assert _feed(_cutter(), levels, echo_at={1}) == [([2, 3, 4, 5], 0.1, 0.5)]


# --- the bar under ordinary speech --------------------------------------------


def _heard(levels, **config):
    """Feed *levels*; the levels of the blocks of each utterance found."""
    finished = _feed(_cutter(**config), levels)
    return [[levels[block] for block in blocks] for blocks, _, _ in finished]


ROOM = [0.08] * 5  # the room, heard while zrb was silent


def test_a_room_loud_enough_to_lift_the_bar_opens_no_turn():
    """A conversation going on around the microphone is not the user: over
    enough of a background it stops reaching the threshold at all."""
    assert _heard(ROOM + [0.15] * 3 + [0.0] * 3) == []


def test_a_block_that_heard_nothing_does_not_floor_the_room_at_zero():
    """A dropped buffer reads 0, which is not the room being quiet: one of them
    must not hand the whole window back to the threshold."""
    assert _heard(ROOM + [0.0] + [0.15] * 3 + [0.0] * 3) == []


def test_speech_over_the_room_is_still_heard():
    assert _heard(ROOM + [0.5, 0.5, 0.5, 0.0, 0.0]) == [
        [0.08, 0.08, 0.5, 0.5, 0.5, 0.0, 0.0]
    ]


def test_a_margin_of_zero_counts_the_room_not_at_all():
    assert _heard(ROOM + [0.15] * 3 + [0.0] * 3, noise_margin=0) == [
        [0.08, 0.08, 0.15, 0.15, 0.15, 0.0, 0.0]
    ]


def test_a_quiet_room_leaves_the_bar_at_the_threshold():
    assert _heard([0.0] * 5 + [0.15, 0.15, 0.15, 0.0, 0.0]) == [
        [0.0, 0.0, 0.15, 0.15, 0.15, 0.0, 0.0]
    ]


def test_a_room_with_no_quiet_moment_is_measured_at_its_own_level():
    """Babble that never drops below the threshold: the first utterance is
    heard against the threshold, and the room it taught is what everything
    after it has to clear."""
    finished = _feed(
        _cutter(pre_roll=0, max_utterance=1.0), [0.15] * 13 + [0.0] * 3
    )

    assert len(finished) == 1
    assert len(finished[0][0]) == 10  # cut at max_utterance


def test_a_room_with_no_quiet_moment_is_babble_without_the_margin():
    """The same levels with the room counted not at all: every burst that
    reaches the threshold is heard."""
    finished = _feed(
        _cutter(pre_roll=0, max_utterance=1.0, noise_margin=0),
        [0.15] * 13 + [0.0] * 3,
    )

    assert len(finished) == 2


def test_flush_returns_speech_cut_off_mid_sentence():
    cutter = _cutter()
    _feed(cutter, [0, 1, 1, 1])

    assert cutter.flush(9.0) == ([0, 1, 2, 3], pytest.approx(0.0), 9.0)
    assert cutter.flush(9.0) is None


def test_flush_drops_too_little_speech():
    cutter = _cutter()
    _feed(cutter, [0, 1])

    assert cutter.flush(1.0) is None


# --- listen: the backlog ----------------------------------------------------


async def _collect_with(config, blocks, on_captured=None):
    """Feed every block before the listener reads any, as happens while the
    caller is busy transcribing."""
    captured = {}

    async def consume():
        stream = listen(
            config,
            _holds_for(len(blocks)),
            keep_partial=True,
            on_captured=on_captured,
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        return await task


def _backlog_config(max_backlog):
    return DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0,
        max_backlog=max_backlog,
    )


@pytest.mark.asyncio
async def test_audio_beyond_the_backlog_is_dropped_oldest_first():
    blocks = [
        _block(0.5),
        _block(0.5),
        _block(0.5),
        _block(0.25),
        _block(0.0),
        _block(0.0),
    ]

    utterances = await _collect_with(_backlog_config(0.3), blocks)

    # Only the newest three blocks were kept: the 0.25 one and the silence.
    assert [u.audio for u in utterances] == [_pcm(0.25, 0.25, 0.0, 0.0, 0.0, 0.0)]


@pytest.mark.asyncio
async def test_no_backlog_limit_keeps_everything():
    blocks = [_block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances = await _collect_with(_backlog_config(0), blocks)

    assert [u.audio for u in utterances] == [_pcm(*[0.5] * 4, *[0.0] * 4)]


@pytest.mark.asyncio
async def test_a_negative_backlog_limit_keeps_everything():
    blocks = [_block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances = await _collect_with(_backlog_config(-1), blocks)

    assert [u.audio for u in utterances] == [_pcm(*[0.5] * 4, *[0.0] * 4)]


@pytest.mark.asyncio
async def test_a_one_block_backlog_still_marks_the_gap():
    blocks = [_block(0.5), _block(0.5), _block(0.0)]

    utterances = await _collect_with(_backlog_config(0.1), blocks)

    # Only the last, quiet block survives: no speech, no utterance.
    assert utterances == []


@pytest.mark.asyncio
async def test_speech_is_never_joined_across_dropped_audio():
    """An utterance in progress when audio is dropped is discarded, not
    spliced onto what comes after the gap."""
    captured = {}
    config = _backlog_config(0.2)

    async def consume():
        stream = listen(config, _holds_for(5), keep_partial=True)
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, [_block(0.5)])  # read at once: speech starts
        await asyncio.sleep(0.01)
        # Then three more arrive at once; with room for two, one is dropped.
        await _play(captured, [_block(0.25), _block(0.75), _block(0.75)])
        utterances = await task

    assert [u.audio for u in utterances] == [_pcm(0.75, 0.75, 0.75, 0.75)]


def test_the_block_duration_is_what_every_duration_is_counted_in():
    # 0.2 s blocks: 0.4 s of silence is two quiet blocks.
    cutter = UtteranceCutter(
        DictationConfig(
            block_duration=0.2,
            threshold=0.1,
            silence=0.4,
            min_speech=0.2,
            pre_roll=0,
        ).resolve()
    )
    finished = [cutter.feed(i, level, i * 0.2, False) for i, level in enumerate([1, 0])]
    assert finished == [None, None]
    assert cutter.quiet_seconds == pytest.approx(0.2)
    assert cutter.feed(2, 0, 0.4, False) is not None


def test_a_block_duration_that_is_not_positive_is_refused():
    with pytest.raises(ValueError, match="BLOCK_DURATION"):
        UtteranceCutter(DictationConfig(block_duration=0).resolve())
