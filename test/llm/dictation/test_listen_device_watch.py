"""`listen` and a change in the audio devices: a microphone or speakers
plugged, unplugged or made the default, while the listening is already going.

The microphone is a fake `sounddevice` whose device view changes mid-listen;
which stream gets opened, and whether the device view is even read, is what
the test sees.
"""

import asyncio
import contextlib
import time
from contextlib import aclosing
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import listen

np = pytest.importorskip("numpy")


class FakeSoundDevice:
    """A `sounddevice` with a readable device view, which opens what it is
    asked for when a stream is. *default_in* is what `query_devices` answers
    for the default microphone (`kind="input"`), what a stream with no
    *device* would open."""

    def __init__(self):
        self.devices = [
            {"name": "BuiltIn", "max_input_channels": 2, "max_output_channels": 0},
            _airpods(),
        ]
        self.default_in = 0
        self.default_out = 1
        self.opened: list = []
        self.is_queried = False

    def query_devices(self, device=None, kind=None):
        self.is_queried = True
        entries = [
            {**device, "index": index} for index, device in enumerate(self.devices)
        ]
        if device is None and kind is not None:
            return entries[self.default_in if kind == "input" else self.default_out]
        return entries

    def InputStream(self, **kwargs):
        stream = FakeStream()
        stream.callback = kwargs["callback"]
        self.opened.append((stream, dict(kwargs)))
        return stream


class FakeStream:
    """A `sounddevice.InputStream`, started by `listen` and closed by it."""

    def __init__(self):
        self.active = True
        self.is_started = False
        self.is_closed = False

    def start(self):
        self.is_started = True

    def close(self):
        self.is_closed = True


class _FakeEchoCancelledMicrophone(FakeStream):
    """Stands in for macOS voice processing."""

    instances: list = []

    def __init__(self, np_module, callback, samplerate, blocksize):
        super().__init__()
        self.callback = callback
        self.blocksize = blocksize
        _FakeEchoCancelledMicrophone.instances.append(self)

    async def confirm_audio(self, timeout):
        return None


def _wait_for(condition, timeout=5.0):
    """Wait on the event loop until *condition* holds, what keeps tests from
    racing the parts of `listen` that run on threads of their own."""
    deadline = time.monotonic() + timeout

    async def wait():
        while not condition():
            if time.monotonic() > deadline:
                raise AssertionError("the condition did not hold in time")
            await asyncio.sleep(0.01)

    return wait()


async def _listen(sounddevice, config, is_listening):
    gen = listen(config, lambda: is_listening[0])
    async with aclosing(gen) as microphone:
        return [utterance async for utterance in microphone]


@contextlib.contextmanager
def _patched(sounddevice):
    with (
        patch.dict("sys.modules", {"sounddevice": sounddevice}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
        # The loop asks as often as it turns, so a change is what a test
        # sets it to, not what the wait says.
        patch("zrb.llm.dictation.listen.DEVICE_WATCH_SECONDS", 0.0),
    ):
        yield


def _airpods():
    return {"name": "AirPods", "max_input_channels": 2, "max_output_channels": 2}


def _listen_config(**overrides):
    # 0.01 s blocks: the idle loop turns every 0.05 s.
    return DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0.1,
        block_duration=0.01,
        **overrides,
    )


@pytest.mark.asyncio
async def test_a_device_change_while_listening_reopens_the_microphone(caplog):
    """Hands-free listening keeps the stream it opened as long as the
    hardware says the same. When the devices change (a headset is plugged
    in, or made the microphone over the old one), the stream is closed and
    opened again, on the devices there now."""
    sounddevice = FakeSoundDevice()
    is_listening = [True]

    async def change_the_devices():
        await _wait_for(lambda: len(sounddevice.opened) == 1)
        await asyncio.sleep(0.05)  # a check or two against the unchanged view
        sounddevice.devices.append(_airpods())
        await _wait_for(lambda: len(sounddevice.opened) == 2)
        is_listening[0] = False

    with _patched(sounddevice):
        task = asyncio.create_task(_listen(sounddevice, _listen_config(), is_listening))
        await asyncio.wait_for(change_the_devices(), timeout=5)
        utterances = await asyncio.wait_for(task, timeout=5)

    [first, second] = [stream for stream, _ in sounddevice.opened]
    assert first.is_closed and first.is_started
    assert second.is_started and second.is_closed
    assert utterances == []
    assert "The audio devices changed" in caplog.text


@pytest.mark.asyncio
async def test_an_operating_system_default_change_reopens_the_microphone(caplog):
    """The OS moved its default microphone to a device that was there all
    along: the device list says the same, but the resolved default the
    watch follows does not, and the stream is reopened on what the OS says
    now."""
    sounddevice = FakeSoundDevice()
    is_listening = [True]

    async def make_it_the_default():
        await _wait_for(lambda: len(sounddevice.opened) == 1)
        await asyncio.sleep(0.05)  # a check or two against the unchanged view
        sounddevice.default_in = 1
        await _wait_for(lambda: len(sounddevice.opened) == 2)
        is_listening[0] = False

    with _patched(sounddevice):
        task = asyncio.create_task(_listen(sounddevice, _listen_config(), is_listening))
        await asyncio.wait_for(make_it_the_default(), timeout=5)
        utterances = await asyncio.wait_for(task, timeout=5)

    [first, second] = [stream for stream, _ in sounddevice.opened]
    assert first.is_closed
    assert second.is_started and second.is_closed
    assert utterances == []
    assert "The audio devices changed" in caplog.text
    # The device view was unchanged: only the resolved default moved.
    assert [d["name"] for d in sounddevice.query_devices()] == ["BuiltIn", "AirPods"]


@pytest.mark.asyncio
async def test_a_change_while_audio_keeps_arriving_reopens_the_microphone(caplog):
    """The watch does not wait for the quiet: with the microphone producing
    blocks without a pause — the loop never seeing an empty timeout — a
    device change still closes the old stream and opens the new one."""
    sounddevice = FakeSoundDevice()
    is_listening = [True]

    async def speak_through_the_change():
        await _wait_for(lambda: len(sounddevice.opened) == 1)
        [stream] = [stream for stream, _ in sounddevice.opened]
        for index in range(30):
            stream.callback(_loud_block(), 2, None, None)
            if index == 10:
                sounddevice.default_in = 1
            await asyncio.sleep(0.01)
            # The reopen answered while the blocks kept coming.
            if len(sounddevice.opened) == 2:
                break
        assert len(sounddevice.opened) == 2

    with _patched(sounddevice):
        task = asyncio.create_task(_listen(sounddevice, _listen_config(), is_listening))
        await asyncio.wait_for(speak_through_the_change(), timeout=5)
        is_listening[0] = False
        await asyncio.wait_for(task, timeout=5)

    [first, second] = [stream for stream, _ in sounddevice.opened]
    assert first.is_closed
    assert second.is_started and second.is_closed
    assert "The audio devices changed" in caplog.text


def _loud_block():
    return np.full((2, 1), 1.0, dtype=np.float32)


@pytest.mark.asyncio
async def test_a_microphone_named_in_the_setting_is_not_moved_for_a_change():
    """When the user names the microphone, a speaker being plugged in has no
    business closing its stream: the devices are PortAudio's to watch, but
    the setting says which microphone. The device view is not even read."""
    sounddevice = FakeSoundDevice()
    is_listening = [True]

    with _patched(sounddevice):
        task = asyncio.create_task(
            _listen(sounddevice, _listen_config(device="usb"), is_listening)
        )
        await _wait_for(lambda: len(sounddevice.opened) == 1)
        await asyncio.sleep(0.05)  # the idle loop turns against the same view
        sounddevice.devices.append(_airpods())
        await asyncio.sleep(0.05)  # as many turns again, still not moved
        assert len(sounddevice.opened) == 1
        assert not sounddevice.is_queried
        is_listening[0] = False
        await asyncio.wait_for(task, timeout=5)

    assert len(sounddevice.opened) == 1


@pytest.mark.asyncio
async def test_the_echo_cancelled_microphone_is_not_reopened_for_a_change():
    """macOS voice processing has its own relation to a device change, which
    `listen` reopens from when the engine dies on it; while the engine is
    alive, the change of some other device does not break its stream."""
    sounddevice = FakeSoundDevice()
    is_listening = [True]
    _FakeEchoCancelledMicrophone.instances = []

    async def change_the_devices():
        await _wait_for(lambda: len(_FakeEchoCancelledMicrophone.instances) == 1)
        await asyncio.sleep(0.05)
        sounddevice.devices.append(_airpods())
        await asyncio.sleep(0.1)
        assert len(_FakeEchoCancelledMicrophone.instances) == 1
        is_listening[0] = False

    with (
        _patched(sounddevice),
        patch("zrb.llm.dictation.listen.get_unavailable_reason", return_value=None),
        patch(
            "zrb.llm.dictation.listen.EchoCancelledMicrophone",
            _FakeEchoCancelledMicrophone,
        ),
    ):
        task = asyncio.create_task(
            _listen(sounddevice, _listen_config(enable_echo_cancel=True), is_listening)
        )
        await asyncio.wait_for(change_the_devices(), timeout=5)
        await asyncio.wait_for(task, timeout=5)

    assert sounddevice.opened == []  # the plain microphone never opened
    assert _FakeEchoCancelledMicrophone.instances[0].is_closed
    assert not sounddevice.is_queried
