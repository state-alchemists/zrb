"""A CoreAudio call that never comes back writes the device off for the rest of
the process.

The deadlock itself is inside CoreAudio: PortAudio's stop waits on a lock the
audio thread holds and wants back, and `Pa_OpenStream` queues behind both. zrb
cannot undo it, but it can refuse to lead every later sentence into it — the
sentences after the one that hit it are said by a player program, in a process
of its own, which shares no lock with this one.
"""

import threading
import time
import types
from unittest.mock import patch

import pytest

from zrb.llm.speech import pcm_player
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.pcm_player import PcmUtterance

from .test_pcm_player import CallbackStop, FakeOutputStream
from .test_pcm_player_exit import SlowStopStream

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


class ProgramUtterance(Utterance):
    """A player program standing in for the fallback."""

    def __init__(self, events):
        super().__init__([])
        self.events = events

    def play(self, timeout):
        self.events.append("played")


def _hang_the_stop(sd, monkeypatch):  # noqa: F811
    SlowStopStream.release = threading.Event()
    SlowStopStream.stopping = threading.Event()
    sd.OutputStream = SlowStopStream
    monkeypatch.setattr(pcm_player, "STREAM_STOP_TIMEOUT_SECONDS", 0.05)


def _play_one_sentence():
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]), on_device_error=lambda error: None
    )
    utterance.play(timeout=5)


def _let_the_stop_finish(sd):  # noqa: F811
    SlowStopStream.release.set()
    pcm_player.wait_for_streams_to_close(2)


def test_a_stop_that_runs_out_the_clock_writes_the_device_off(
    sd, monkeypatch
):  # noqa: F811
    _hang_the_stop(sd, monkeypatch)

    _play_one_sentence()
    was_wedged = pcm_player.is_device_wedged()

    _let_the_stop_finish(sd)

    assert was_wedged


def test_a_wedged_device_is_not_opened_again(sd, monkeypatch):  # noqa: F811
    _hang_the_stop(sd, monkeypatch)

    _play_one_sentence()
    _let_the_stop_finish(sd)
    opened_before = len(FakeOutputStream.instances)

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        _play_one_sentence()
    elapsed = time.monotonic() - started

    assert len(FakeOutputStream.instances) == opened_before
    assert elapsed < 1


def test_a_wedged_device_says_the_sentence_through_a_player_program(
    sd, monkeypatch
):  # noqa: F811
    _hang_the_stop(sd, monkeypatch)

    _play_one_sentence()
    _let_the_stop_finish(sd)
    events: list[str] = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: ProgramUtterance(events),
        on_device_error=lambda error: None,
    )

    utterance.play(timeout=5)

    assert events == ["played"]


def test_an_open_that_runs_out_the_clock_writes_the_device_off(
    sd, monkeypatch
):  # noqa: F811
    from .test_pcm_player_open_timeout import SlowOpenStream

    SlowOpenStream.release = threading.Event()
    SlowOpenStream.opening = threading.Event()
    sd.OutputStream = SlowOpenStream
    monkeypatch.setattr(pcm_player, "STREAM_OPEN_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(TimeoutError):
        _play_one_sentence()
    was_wedged = pcm_player.is_device_wedged()

    SlowOpenStream.release.set()
    pcm_player.wait_for_streams_to_close(2)

    assert was_wedged
