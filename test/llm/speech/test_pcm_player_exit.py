"""`PcmUtterance` and the process ending: an output stream counts as open from
the moment it is constructed until it is closed, so the exit handler can wait
for one still being stopped before PortAudio terminates."""

import threading
import time
import types
from unittest.mock import patch

import pytest

from zrb.llm.speech import pcm_player
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.pcm_player import PcmUtterance

from .test_pcm_player import CallbackStop, FakeOutputStream

RATE = 16000

np = pytest.importorskip("numpy")


@pytest.fixture
def sd():
    FakeOutputStream.instances = []
    fake = types.SimpleNamespace(
        OutputStream=FakeOutputStream, CallbackStop=CallbackStop
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        yield fake


def _pcm(values):
    return np.array(values, np.int16).tobytes()


class SlowStopStream(FakeOutputStream):
    """A stream whose stop takes until it is released, as CoreAudio's can when
    two threads stop one at once."""

    release = threading.Event()
    stopping = threading.Event()

    def stop(self):
        SlowStopStream.stopping.set()
        SlowStopStream.release.wait(5)
        super().stop()


def test_nothing_waits_when_no_stream_is_open(sd):
    pcm_player.wait_for_streams_to_close(0.01)

    assert not pcm_player.has_open_streams()


def test_a_stream_still_stopping_is_waited_for(sd):
    SlowStopStream.release = threading.Event()
    SlowStopStream.stopping = threading.Event()
    sd.OutputStream = SlowStopStream
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 256)]))
    player = threading.Thread(target=utterance.play, args=(5,))
    player.start()
    assert SlowStopStream.stopping.wait(5)

    pcm_player.wait_for_streams_to_close(0.05)
    open_while_stopping = pcm_player.has_open_streams()
    SlowStopStream.release.set()
    player.join(5)
    pcm_player.wait_for_streams_to_close(1)

    assert open_while_stopping
    assert not pcm_player.has_open_streams()


def test_a_stream_counts_as_open_from_the_moment_it_is_constructed(sd):
    """A constructed `OutputStream` is already an open PortAudio stream, so an
    exit handler asking just then has to see it."""
    seen: list[bool] = []

    class WatchingStream(FakeOutputStream):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen.append(pcm_player.has_open_streams())

    sd.OutputStream = WatchingStream

    PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 256)])).play(timeout=5)

    assert seen == [True]
    assert not pcm_player.has_open_streams()


def test_a_device_that_cannot_be_constructed_leaves_no_stream_counted(sd):
    def refuse(*args, **kwargs):
        raise OSError("no device")

    sd.OutputStream = refuse

    with pytest.raises(OSError):
        PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 256)])).play(timeout=5)

    assert not pcm_player.has_open_streams()


class StrictStream(FakeOutputStream):
    """A stream that treats `CallbackStop` as what it is to PortAudio: the audio
    thread stopping the stream itself. On macOS that races the playing thread's
    own stop on the same stream and deadlocks CoreAudio."""

    raised: list = []
    # How long the playing thread's stop takes to land: the audio thread asks
    # for another block in the meantime, as it does on a real device.
    stop_latency = 0.05

    def stop(self):
        time.sleep(StrictStream.stop_latency)
        super().stop()

    def _run(self):
        while self._running:
            out = np.zeros((self.blocksize, 1), np.int16)
            try:
                self.callback(out, self.blocksize, None, None)
            except BaseException as exc:
                StrictStream.raised.append(exc)
                break
            time.sleep(0.001)
        self.finished()


def _play_on_strict_stream(sd, utterance, stop_after=None):
    StrictStream.raised = []
    sd.OutputStream = StrictStream
    player = threading.Thread(target=utterance.play, args=(5,))
    player.start()
    if stop_after is not None:
        time.sleep(stop_after)
        utterance.stop()
    player.join(5)
    assert not player.is_alive()


def test_the_callback_does_not_stop_the_stream_when_the_audio_ends(sd):
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 512)]))

    _play_on_strict_stream(sd, utterance)

    assert StrictStream.raised == []


def test_the_callback_does_not_stop_the_stream_when_it_is_stopped(sd):
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 512)] * 400))

    _play_on_strict_stream(sd, utterance, stop_after=0.05)

    assert StrictStream.raised == []
