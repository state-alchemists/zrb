"""The microphone itself: opening it, which device it opens, and recording.

`listen` and `record` both go through `_open_microphone`, so this is where a
device that will not start is retried, and where the report says which device it
was asked for and what names another. The microphone is a fake `sounddevice`
whose `InputStream` hands its callback to the test, which then plays blocks into
it.
"""

import asyncio
from contextlib import aclosing
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import listen, record

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


def _listen_config(**overrides):
    # 0.1 s blocks: speech starts at a loud block and ends after 2 quiet ones.
    return DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0.1,
        **overrides,
    )


async def _captured_stream_options(config, blocks):
    """Drive one `listen` over *blocks*, returning what `InputStream` was asked
    for alongside the utterances it produced."""
    captured = {}

    async def consume():
        stream = listen(config, _holds_for(len(blocks)))
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        return await task, captured


# --- record ------------------------------------------------------------------


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


# --- opening the microphone --------------------------------------------------


@pytest.mark.asyncio
async def test_the_device_it_was_asked_for_reaches_portaudio():
    """`device` reaches PortAudio.

    Which device PortAudio opens is the usual difference between a microphone
    that starts and one that times out — `pulse` and `default` on a Linux or WSL
    machine are not the same microphone — so the setting that names one has to
    arrive.
    """
    utterances, captured = await _captured_stream_options(
        _listen_config(device="pulse"), [_block(0.0)]
    )

    assert utterances == []
    assert captured["device"] == "pulse"


@pytest.mark.asyncio
async def test_a_start_that_fails_is_tried_again():
    """One miss at starting the microphone does not end the listening.

    PortAudio gives the thread it starts one second to come up and reports
    `paTimedOut` when it misses; a machine that stalls misses it, for reasons
    that have nothing to do with zrb, and the stall is over by the time the call
    returns.
    """
    captured = {}
    started = []

    class FlakyStream(FakeStream):
        def start(self):
            started.append(self)
            if len(started) == 1:
                raise RuntimeError("Error starting stream: Wait timed out")
            super().start()

    def make_stream(**kwargs):
        captured.update(kwargs)
        return FlakyStream()

    flaky_sd = MagicMock()
    flaky_sd.InputStream.side_effect = make_stream
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    async def consume():
        stream = listen(_listen_config(), _holds_for(len(blocks)), keep_partial=True)
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": flaky_sd}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        utterances = await task

    assert len(utterances) == 1
    assert len(started) == 2
    # The stream that never started was closed before another was tried.
    assert started[0].is_closed
    assert started[1].is_started


@pytest.mark.asyncio
async def test_a_microphone_that_will_not_start_says_which_device_it_tried():
    """The device is named, because the PortAudio message alone does not say it.

    "Wait timed out" with `PaErrorCode -9987` says nothing about what to change;
    the device PortAudio was asked for, and the setting that names another, are
    the difference between a report a user can act on and one they cannot.
    """

    class DeadStream(FakeStream):
        def start(self):
            raise RuntimeError("Error starting stream: Wait timed out")

    dead_sd = MagicMock()
    dead_sd.InputStream.side_effect = lambda **kwargs: DeadStream()

    with patch.dict("sys.modules", {"sounddevice": dead_sd}):
        with pytest.raises(RuntimeError) as raised:
            async with aclosing(
                listen(_listen_config(device="pulse"), _holds_for(1))
            ) as mic:
                await anext(mic)

    message = str(raised.value)
    assert "Error starting stream: Wait timed out" in message
    assert "device 'pulse'" in message
    assert "LLM_DICTATION_DEVICE" in message
