"""`listen` and `record` through macOS echo cancellation: the voice-processing
microphone standing in for sounddevice's, and every way it falls back to the
plain one.

`EchoCancelledMicrophone` is replaced by a fake that hands its callback to the
test; the plain microphone is a fake `sounddevice` that does the same.
"""

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import listen, record

np = pytest.importorskip("numpy")


class FakeStream:
    """A `sounddevice.InputStream`, or the echo-cancelled microphone's base."""

    def __init__(self):
        self.is_started = False
        self.is_closed = False
        self.active = True

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


class _FakeEchoCancelledMicrophone(FakeStream):
    """Stands in for macOS voice processing; *fails* makes start raise, and
    *is_silent* makes it start but hear nothing (a Bluetooth headset)."""

    fails = False
    is_silent = False
    close_fails = False
    instances: list = []

    def __init__(self, np_module, callback, samplerate, blocksize):
        super().__init__()
        self.callback = callback
        self.blocksize = blocksize
        _FakeEchoCancelledMicrophone.instances.append(self)

    def start(self):
        if self.fails:
            raise RuntimeError("voice processing would not start")
        super().start()

    def close(self):
        super().close()
        if self.close_fails:
            raise RuntimeError("Releasing the echo-cancelled microphone failed")

    async def confirm_audio(self, timeout):
        if self.is_silent:
            raise RuntimeError("The echo-cancelled microphone heard nothing")


async def _collect_echo_cancelled(
    blocks, reason=None, fails=False, device=None, is_silent=False, close_fails=False
):
    """Run `listen` with echo cancellation asked for; returns the utterances,
    what sounddevice was asked for, and the voice-processing microphones."""
    captured = {}
    _FakeEchoCancelledMicrophone.instances = []
    _FakeEchoCancelledMicrophone.fails = fails
    _FakeEchoCancelledMicrophone.is_silent = is_silent
    _FakeEchoCancelledMicrophone.close_fails = close_fails
    config = _listen_config(enable_echo_cancel=True, device=device)

    async def consume():
        stream = listen(config, _holds_for(len(blocks)))
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
        patch("zrb.llm.dictation.listen.get_unavailable_reason", return_value=reason),
        patch(
            "zrb.llm.dictation.listen.EchoCancelledMicrophone",
            _FakeEchoCancelledMicrophone,
        ),
    ):
        task = asyncio.create_task(consume())
        microphones = _FakeEchoCancelledMicrophone.instances
        will_hear_through_voice_processing = reason is None and not (fails or is_silent)

        def feed_ready() -> bool:
            if will_hear_through_voice_processing:
                return bool(microphones) and hasattr(microphones[0], "callback")
            return "callback" in captured

        # How many loop turns `listen` needs before its input is open depends
        # on the path it takes (a silent microphone is confirmed first, then the
        # fallback opens PortAudio), so wait for the callback instead of
        # guessing a count. A task that dies first stops the wait too.
        for _ in range(2000):
            if feed_ready() or task.done():
                break
            await asyncio.sleep(0.001)
        if will_hear_through_voice_processing:
            feed = microphones[0].callback
        else:
            feed = captured["callback"]
        for block in blocks:
            feed(block, len(block), None, None)
        return await task, captured, microphones


@pytest.mark.asyncio
async def test_listen_hears_through_voice_processing_when_echo_cancel_is_on():
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, captured, microphones = await _collect_echo_cancelled(blocks)

    assert len(utterances) == 1
    assert captured == {}  # sounddevice never opened
    assert microphones[0].is_started and microphones[0].is_closed
    assert microphones[0].blocksize == 1600


@pytest.mark.asyncio
async def test_listen_falls_back_to_portaudio_when_voice_processing_fails(caplog):
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, captured, _ = await _collect_echo_cancelled(blocks, fails=True)

    assert len(utterances) == 1
    assert captured["blocksize"] == 1600
    assert "without echo cancellation" in caplog.text


@pytest.mark.asyncio
async def test_listen_says_why_echo_cancel_is_unavailable(caplog):
    blocks = [_block(0.0), _block(0.0)]

    _, captured, microphones = await _collect_echo_cancelled(
        blocks, reason="a reason only this test gives", device="2"
    )

    assert microphones == []
    assert captured["device"] == 2
    assert "Echo cancellation is off: a reason only this test gives" in caplog.text


@pytest.mark.asyncio
async def test_listen_falls_back_when_voice_processing_hears_nothing(caplog):
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, captured, microphones = await _collect_echo_cancelled(
        blocks, is_silent=True
    )

    assert len(utterances) == 1
    assert captured["blocksize"] == 1600
    assert microphones[0].is_closed
    assert "heard nothing" in caplog.text


@pytest.mark.asyncio
async def test_listen_opens_the_plain_microphone_even_when_releasing_fails(caplog):
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, captured, _ = await _collect_echo_cancelled(
        blocks, is_silent=True, close_fails=True
    )

    assert len(utterances) == 1
    assert captured["blocksize"] == 1600
    assert "opening the plain microphone anyway" in caplog.text


@pytest.mark.asyncio
async def test_record_with_a_config_records_through_echo_cancellation():
    _FakeEchoCancelledMicrophone.instances = []
    _FakeEchoCancelledMicrophone.fails = False
    _FakeEchoCancelledMicrophone.is_silent = False
    _FakeEchoCancelledMicrophone.close_fails = False
    captured = {}
    config = _listen_config(enable_echo_cancel=True)

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.get_unavailable_reason", return_value=None),
        patch(
            "zrb.llm.dictation.listen.EchoCancelledMicrophone",
            _FakeEchoCancelledMicrophone,
        ),
    ):
        task = asyncio.create_task(record(_holds_for(3), config))
        await asyncio.sleep(0)
        microphone = _FakeEchoCancelledMicrophone.instances[0]
        microphone.callback(_block(0.5), 2, None, None)
        audio = await task

    assert audio == _pcm(0.5, 0.5)
    assert captured == {}  # sounddevice never opened
    assert microphone.is_closed


def _reset_fake_echo_microphone(**flags):
    _FakeEchoCancelledMicrophone.instances = []
    for flag in ("fails", "is_silent", "close_fails"):
        setattr(_FakeEchoCancelledMicrophone, flag, flags.get(flag, False))


def _patch_echo_cancel(captured):
    return (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
        patch("zrb.llm.dictation.listen.get_unavailable_reason", return_value=None),
        patch(
            "zrb.llm.dictation.listen.EchoCancelledMicrophone",
            _FakeEchoCancelledMicrophone,
        ),
    )


@pytest.mark.asyncio
async def test_record_falls_back_when_voice_processing_hears_nothing():
    _reset_fake_echo_microphone(is_silent=True)
    captured = {}
    first, second, third, fourth = _patch_echo_cancel(captured)

    with first, second, third, fourth:
        task = asyncio.create_task(
            record(_holds_for(3), _listen_config(enable_echo_cancel=True))
        )
        await asyncio.sleep(0)
        captured["callback"](_block(0.5), 2, None, None)
        audio = await task

    assert audio == _pcm(0.5, 0.5)
    assert _FakeEchoCancelledMicrophone.instances[0].is_closed


@pytest.mark.asyncio
async def test_listen_finishes_when_the_microphone_fails_to_release(caplog):
    blocks = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    utterances, _, microphones = await _collect_echo_cancelled(blocks, close_fails=True)

    assert len(utterances) == 1
    assert microphones[0].is_closed
    assert "Closing the microphone failed" in caplog.text


@pytest.mark.asyncio
async def test_listen_carries_on_without_echo_cancel_once_it_dies(caplog):
    _reset_fake_echo_microphone()
    captured = {}
    config = _listen_config(enable_echo_cancel=True)
    speech = [_block(0.0), _block(0.5), _block(0.5), _block(0.0), _block(0.0)]

    async def consume():
        # One check finds the echo-cancelled stream dead; the rest read speech.
        stream = listen(config, _holds_for(len(speech) + 1))
        return [utterance async for utterance in stream]

    first, second, third, fourth = _patch_echo_cancel(captured)
    with first, second, third, fourth:
        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        _FakeEchoCancelledMicrophone.instances[0].active = False  # route change
        while "callback" not in captured:
            await asyncio.sleep(0.05)
        for block in speech:
            captured["callback"](block, len(block), None, None)
        utterances = await asyncio.wait_for(task, timeout=5)

    assert len(utterances) == 1
    assert len(_FakeEchoCancelledMicrophone.instances) == 1  # never retried
    assert "without echo cancellation until" in caplog.text


@pytest.mark.asyncio
async def test_a_microphone_that_is_slow_to_close_does_not_block_the_event_loop():
    closing = threading.Event()
    release = threading.Event()

    class SlowClose(FakeStream):
        def close(self):
            closing.set()
            # Core Audio's teardown can take this long; the thread waits here.
            release.wait(timeout=5)
            super().close()

    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = lambda **kwargs: SlowClose()

    async def consume():
        return [u async for u in listen(_listen_config(), lambda: False)]

    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        task = asyncio.create_task(consume())
        try:
            for _ in range(200):
                if closing.is_set():
                    break
                await asyncio.sleep(0.01)
            assert closing.is_set()
            # The loop still turns while the close is stuck.
            await asyncio.wait_for(asyncio.sleep(0.05), timeout=1)
            assert not task.done()
        finally:
            release.set()
        assert await asyncio.wait_for(task, timeout=5) == []
