"""Barge-in: `UtteranceCutter` and `listen` hearing the user talk over zrb.

The microphone is a fake `sounddevice` whose `InputStream` hands its callback
to the test, which then plays blocks into it.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import MicState, UtteranceCutter, listen

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
    remaining = [checks]

    def should_continue():
        remaining[0] -= 1
        return remaining[0] >= 0

    return should_continue


def _block(value):
    return np.full((2, 1), value, dtype=np.float32)


async def _play(captured, blocks):
    await asyncio.sleep(0)  # let the coroutine open the stream
    for block in blocks:
        captured["callback"](block, len(block), None, None)


def _cutter(**config):
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
    utterances as (blocks, started_at, ended_at), times rounded."""
    finished = []
    for index, level in enumerate(levels):
        done = cutter.feed(index, level, index / 10, index in echo_at)
        if done is not None:
            blocks, started_at, ended_at = done
            finished.append((blocks, round(started_at, 6), round(ended_at, 6)))
    return finished


def test_without_barge_in_speech_over_zrb_is_never_heard():
    cutter = _cutter()
    assert _feed(cutter, [1, 1, 1, 0, 0, 0], echo_at={0, 1, 2}) == []
    assert not cutter.is_barge_in_enabled


def test_with_barge_in_speech_over_zrb_is_heard_and_marked():
    cutter = _cutter(barge_in="headset", barge_in_min_speech=0.2, pre_roll=0)

    finished = _feed(cutter, [1, 1, 1, 0, 0, 0], echo_at={0, 1, 2, 3, 4, 5})

    assert finished == [([0, 1, 2, 3, 4], -0.1, 0.4)]
    assert cutter.is_finished_barge_in
    # Between utterances nothing is talking over zrb.
    assert not cutter.is_barge_in


def test_a_cough_over_zrb_is_not_a_barge_in():
    cutter = _cutter(barge_in="headset", barge_in_min_speech=0.3, pre_roll=0)

    _feed(cutter, [1, 1, 0, 0, 0], echo_at={0, 1, 2, 3, 4})

    assert not cutter.is_barge_in
    assert not cutter.is_finished_barge_in


def test_speech_after_zrb_stopped_is_not_a_barge_in():
    cutter = _cutter(barge_in="headset", barge_in_min_speech=0.1, pre_roll=0)

    finished = _feed(cutter, [1, 1, 0, 0, 0, 1, 1, 0, 0], echo_at={0, 1})

    assert len(finished) == 2
    assert not cutter.is_finished_barge_in


@pytest.mark.asyncio
async def test_listen_reports_a_barge_in_once_before_the_utterance_ends():
    captured = {}
    events = []
    config = DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0,
        echo_cooldown=0,
        barge_in="headset",
        barge_in_min_speech=0.1,
    ).resolve()
    blocks = [_block(0.5), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    async def consume():
        stream = listen(
            config,
            _holds_for(len(blocks)),
            on_barge_in=lambda: events.append("barge_in"),
            on_state=lambda state: events.append(state),
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=True),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        utterances = await task

    assert events.count("barge_in") == 1
    assert MicState.PAUSED not in events
    assert [u.is_barge_in for u in utterances] == [True]


def test_a_barge_in_is_forgotten_when_its_utterance_is_dropped():
    cutter = _cutter(barge_in="headset", barge_in_min_speech=0.1, pre_roll=0)
    _feed(cutter, [1, 1, 1], echo_at={0, 1, 2})
    assert cutter.is_barge_in

    cutter.reset()

    assert not cutter.is_barge_in


@pytest.mark.asyncio
async def test_a_barge_in_is_reported_once_and_does_not_mark_the_next_utterance():
    captured = {}
    barge_ins = []
    config = DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0,
        echo_cooldown=0,
        barge_in="headset",
        barge_in_min_speech=0.1,
    ).resolve()
    # Talked over zrb, then idle blocks, then an ordinary utterance after it
    # stopped speaking.
    loud, quiet = _block(0.5), _block(0.0)
    blocks = [loud, loud, quiet, quiet, quiet, quiet, loud, loud, quiet, quiet]
    speaking = iter([True] * 4 + [False] * 6)

    async def consume():
        stream = listen(
            config,
            _holds_for(len(blocks)),
            on_barge_in=lambda: barge_ins.append(True),
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch(
            "zrb.llm.dictation.listen.is_speaking",
            side_effect=lambda: next(speaking),
        ),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        utterances = await task

    assert barge_ins == [True]
    assert [u.is_barge_in for u in utterances] == [True, False]
