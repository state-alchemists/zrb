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
    cutter = _cutter(barge_in_enabled=True, barge_in_min_speech=0.2, pre_roll=0)

    finished = _feed(cutter, [1, 1, 1, 0, 0, 0], echo_at={0, 1, 2, 3, 4, 5})

    assert finished == [([0, 1, 2, 3, 4], -0.1, 0.4)]
    assert cutter.is_finished_barge_in
    # Between utterances nothing is talking over zrb.
    assert not cutter.is_barge_in


def test_a_cough_over_zrb_is_not_a_barge_in():
    cutter = _cutter(barge_in_enabled=True, barge_in_min_speech=0.3, pre_roll=0)

    _feed(cutter, [1, 1, 0, 0, 0], echo_at={0, 1, 2, 3, 4})

    assert not cutter.is_barge_in
    assert not cutter.is_finished_barge_in
    # Still said over zrb: a crisp "stop" is as short as a cough.
    assert cutter.is_finished_over_speech


def test_speech_after_zrb_stopped_is_not_a_barge_in():
    cutter = _cutter(barge_in_enabled=True, barge_in_min_speech=0.1, pre_roll=0)

    finished = _feed(cutter, [1, 1, 0, 0, 0, 1, 1, 0, 0], echo_at={0, 1})

    assert len(finished) == 2
    assert not cutter.is_finished_barge_in
    assert not cutter.is_finished_over_speech


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
        barge_in_enabled=True,
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
    cutter = _cutter(barge_in_enabled=True, barge_in_min_speech=0.1, pre_roll=0)
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
        barge_in_enabled=True,
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


# --- the bar over zrb's voice -------------------------------------------------


def _over_zrb(levels, **config):
    """Feed *levels*, every block captured while zrb speaks; the levels of
    the utterances found, without the two quiet blocks that end each."""
    fields = dict(barge_in_enabled=True, barge_in_margin=3.0, pre_roll=0, silence=0.2)
    cutter = _cutter(**{**fields, **config})
    finished = _feed(cutter, levels, echo_at=set(range(len(levels))))
    return [[levels[block] for block in blocks[:-2]] for blocks, _, _ in finished]


ECHO = [0.12] * 10  # zrb's voice at the microphone, over the 0.1 threshold


def test_zrbs_own_voice_at_its_usual_level_starts_nothing():
    """Laptop speakers: zrb is heard above the usual threshold the whole
    time it speaks, and must not count as the user."""
    assert _over_zrb(ECHO + [0.12] * 20) == []


def test_speech_clearly_louder_than_zrbs_voice_is_heard():
    heard = _over_zrb(ECHO + [0.5, 0.5, 0.5, 0.12, 0.12, 0.12])
    assert heard == [[0.5, 0.5, 0.5]]


def test_speech_only_as_loud_as_zrbs_voice_is_not():
    assert _over_zrb(ECHO + [0.3, 0.3, 0.3, 0.12, 0.12, 0.12]) == []


def test_on_headphones_the_bar_is_the_usual_threshold():
    """zrb is not heard: its measured level is noise, so the bar falls back
    to the threshold and ordinary speech gets through."""
    quiet_room = [0.005] * 10
    assert _over_zrb(quiet_room + [0.2, 0.2, 0.2, 0.0, 0.0]) == [[0.2, 0.2, 0.2]]


def test_before_zrbs_level_is_measured_the_bar_is_strict():
    """The first blocks of zrb speaking: margin times the threshold."""
    assert _over_zrb([0.2, 0.2, 0.2, 0.0, 0.0]) == []
    assert _over_zrb([0.4, 0.4, 0.4, 0.0, 0.0]) == [[0.4, 0.4, 0.4]]


def test_talking_over_zrb_for_long_does_not_raise_the_bar_on_yourself():
    """The user's voice, measured as zrb's while they talk, must not cut
    the utterance they are in."""
    heard = _over_zrb(ECHO + [0.5] * 25 + [0.12, 0.12, 0.12], max_utterance=10)
    assert heard == [[0.5] * 25]


def test_a_long_barge_in_does_not_raise_the_bar_for_the_next_one():
    """Once an utterance is a barge-in, zrb is paused and what the
    microphone hears is the user: learning it as zrb's level would set the
    bar over the user's own voice next time."""
    heard = _over_zrb(
        ECHO + [0.5] * 25 + [0.12] * 5 + [0.5] * 3 + [0.12] * 3, max_utterance=10
    )
    assert heard == [[0.5] * 25, [0.5] * 3]


async def _listen_over_zrb(
    blocks, barge_in_enabled=True, barge_in_min_speech=0.1, **callbacks
):
    captured = {}
    config = DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0,
        barge_in_enabled=barge_in_enabled,
        barge_in_min_speech=barge_in_min_speech,
        barge_in_margin=1.0,
    ).resolve()

    async def consume():
        stream = listen(config, _holds_for(len(blocks)), **callbacks)
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=True),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        return await task


LOUD_THEN_QUIET = [_block(0.5)] * 3 + [_block(0.0)] * 3


@pytest.mark.asyncio
async def test_speech_over_zrb_with_barge_in_off_is_plainly_paused():
    states = []
    utterances = await _listen_over_zrb(
        LOUD_THEN_QUIET, barge_in_enabled=False, on_state=states.append
    )
    assert utterances == [] and states[0] == MicState.PAUSED


@pytest.mark.asyncio
async def test_a_short_word_over_zrb_is_marked_said_over_it_without_pausing_it():
    barge_ins = []
    [utterance] = await _listen_over_zrb(
        [_block(0.5)] + [_block(0.0)] * 4,
        barge_in_min_speech=0.3,
        on_barge_in=lambda: barge_ins.append(True),
    )
    assert utterance.is_over_speech and not utterance.is_barge_in
    assert barge_ins == []


@pytest.mark.asyncio
async def test_a_barge_in_too_short_to_keep_is_reported_dropped():
    events = []
    captured = {}
    config = DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.3,
        max_utterance=10,
        pre_roll=0,
        barge_in_enabled=True,
        barge_in_min_speech=0.1,
        barge_in_margin=1.0,
    ).resolve()
    blocks = [_block(0.5)] + [_block(0.0)] * 4

    async def consume():
        stream = listen(
            config,
            _holds_for(len(blocks)),
            on_barge_in=lambda: events.append("barge_in"),
            on_barge_in_dropped=lambda: events.append("dropped"),
        )
        return [u async for u in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=True),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        assert await task == []

    assert events == ["barge_in", "dropped"]


@pytest.mark.asyncio
async def test_a_yielded_barge_in_is_not_reported_dropped():
    dropped = []
    blocks = LOUD_THEN_QUIET + [_block(0.0)] * 4
    [utterance] = await _listen_over_zrb(
        blocks, on_barge_in_dropped=lambda: dropped.append(True)
    )
    assert utterance.is_barge_in and dropped == []


@pytest.mark.asyncio
async def test_closing_the_microphone_mid_barge_in_reports_it_dropped():
    events = []
    # Loud to the end: the utterance is still in progress when listening stops.
    await _listen_over_zrb(
        [_block(0.5)] * 4,
        on_barge_in=lambda: events.append("barge_in"),
        on_barge_in_dropped=lambda: events.append("dropped"),
    )
    assert events == ["barge_in", "dropped"]
