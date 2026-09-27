"""Tests for `zrb.llm.dictation.listen`.

The microphone is a fake `sounddevice` whose `InputStream` hands its callback
to the test, which then plays blocks into it.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import listen, record

np = pytest.importorskip("numpy")


class FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


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


# --- record -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_returns_captured_blocks_as_int16_pcm():
    captured = {}
    with patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}):
        task = asyncio.create_task(record(_holds_for(2)))
        await _play(captured, [_block(0.5), _block(0.25)])
        result = await task

    assert result == _pcm(0.5, 0.5, 0.25, 0.25)
    assert captured["samplerate"] == 16000
    assert captured["channels"] == 1


@pytest.mark.asyncio
async def test_record_returns_empty_bytes_when_nothing_recorded():
    with patch.dict("sys.modules", {"sounddevice": _fake_sounddevice({})}):
        assert await record(lambda: False) == b""


@pytest.mark.asyncio
async def test_record_keeps_waiting_through_a_silent_microphone():
    with patch.dict("sys.modules", {"sounddevice": _fake_sounddevice({})}):
        assert await record(_holds_for(2)) == b""


@pytest.mark.asyncio
async def test_record_explains_a_microphone_that_will_not_open():
    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = OSError("no device")
    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        with pytest.raises(RuntimeError, match="Cannot open microphone: no device"):
            await record(lambda: True)


# --- listen -----------------------------------------------------------------


def _listen_config():
    # 0.1 s blocks: speech starts at a loud block and ends after 2 quiet ones.
    return DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0.1,
        echo_cooldown=0,
    )


async def _collect(blocks, keep_partial=False, speaking=False):
    captured = {}

    async def consume():
        should_listen = _holds_for(len(blocks))
        stream = listen(_listen_config(), should_listen, keep_partial=keep_partial)
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
async def test_listen_ignores_blocks_captured_while_zrb_speaks():
    blocks = [_block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, _ = await _collect(blocks, keep_partial=True, speaking=True)

    assert utterances == []


# --- UtteranceCutter --------------------------------------------------------


def _cutter(**config):
    from zrb.llm.dictation.listen import UtteranceCutter

    fields = dict(
        threshold=0.1,
        silence=0.2,
        min_speech=0.2,
        max_utterance=1.0,
        pre_roll=0.2,
        echo_cooldown=0.2,
    )
    return UtteranceCutter(DictationConfig(**{**fields, **config}).resolve())


def _feed(cutter, levels, echo_at=()):
    """Feed one block per level (block i captured at i/10 s); the finished
    utterances as (blocks, started_at, ended_at)."""
    finished = []
    for index, level in enumerate(levels):
        done = cutter.feed(index, level, index / 10, index in echo_at)
        if done is not None:
            finished.append(done)
    return finished


def test_speech_ends_after_the_silence_and_keeps_its_pre_roll():
    # pre_roll=0.2 keeps the two quiet blocks before the first loud one.
    finished = _feed(_cutter(), [0, 0, 0, 1, 1, 1, 0, 0, 0])

    assert finished == [([1, 2, 3, 4, 5, 6, 7], 0.3, 0.7)]


def test_zero_pre_roll_keeps_no_quiet_block():
    finished = _feed(_cutter(pre_roll=0), [0, 0, 1, 1, 0, 0])

    assert finished == [([2, 3, 4, 5], 0.2, 0.5)]


def test_zero_max_utterance_means_no_limit():
    finished = _feed(_cutter(max_utterance=0), [1] * 30 + [0, 0])

    assert len(finished) == 1
    assert len(finished[0][0]) == 32  # 30 loud and 2 quiet; nothing came before


def test_a_click_shorter_than_min_speech_is_dropped():
    assert _feed(_cutter(), [0, 1, 0, 0, 0]) == []


def test_speech_is_cut_at_max_utterance():
    (blocks, _, _), *_ = _feed(_cutter(max_utterance=0.5), [1] * 12)

    assert len(blocks) == 5


def test_blocks_while_zrb_speaks_and_the_cooldown_after_are_ignored():
    levels = [1, 1, 1, 1, 0, 0, 0]
    # Echo on block 1 resets the speech; blocks 2 and 3 fall in the cooldown.
    assert _feed(_cutter(), levels, echo_at={1}) == []


def test_flush_returns_speech_cut_off_mid_sentence():
    cutter = _cutter()
    _feed(cutter, [0, 1, 1, 1])

    assert cutter.flush(9.0) == ([0, 1, 2, 3], 0.1, 9.0)
    assert cutter.flush(9.0) is None


def test_flush_drops_too_little_speech():
    cutter = _cutter()
    _feed(cutter, [0, 1])

    assert cutter.flush(1.0) is None
