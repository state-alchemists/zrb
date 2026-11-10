"""An open the audio service never answers must not hold the speech lock.

On 2026-11-10 a wedged CoreAudio device left `Pa_OpenStream` waiting on the HAL
mutex, and it was called while the speech lock was held: every later sentence
waited its thirty seconds and was dropped, so the session went silent and the
only symptom was silence. `_open_stream_in_time` gives that call a deadline,
closes a stream that arrives after it, and reports the device unusable.
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


class SlowOpenStream(FakeOutputStream):
    """A stream whose construction waits until it is released: `Pa_OpenStream`
    on a device the audio service is deadlocked over."""

    release = threading.Event()
    opening = threading.Event()

    def __init__(self, *args, **kwargs):
        SlowOpenStream.opening.set()
        SlowOpenStream.release.wait(5)
        super().__init__(*args, **kwargs)


def _hang_the_open(sd, monkeypatch):
    SlowOpenStream.release = threading.Event()
    SlowOpenStream.opening = threading.Event()
    sd.OutputStream = SlowOpenStream
    monkeypatch.setattr(pcm_player, "STREAM_OPEN_TIMEOUT_SECONDS", 0.05)


def test_an_open_that_never_returns_is_given_up_on(sd, monkeypatch):
    _hang_the_open(sd, monkeypatch)
    device_errors: list[Exception] = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]), on_device_error=device_errors.append
    )

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        utterance.play(timeout=5)
    elapsed = time.monotonic() - started

    SlowOpenStream.release.set()
    pcm_player.wait_for_streams_to_close(2)

    assert elapsed < 2
    assert [type(error) for error in device_errors] == [TimeoutError]


def test_a_stream_that_arrives_after_the_deadline_is_closed(sd, monkeypatch):
    """The abandoned open still finishes eventually; what it returns is a device
    nothing plays into, so it goes back the moment it arrives."""
    _hang_the_open(sd, monkeypatch)
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]), on_device_error=lambda error: None
    )

    with pytest.raises(TimeoutError):
        utterance.play(timeout=5)
    open_while_stuck = pcm_player.has_open_streams()
    SlowOpenStream.release.set()
    pcm_player.wait_for_streams_to_close(2)

    assert open_while_stuck
    assert not pcm_player.has_open_streams()


class ProgramUtterance(Utterance):
    """A player program standing in for the fallback."""

    def __init__(self, events):
        super().__init__([])
        self.events = events

    def play(self, timeout):
        self.events.append("played")


def test_a_hung_open_hands_the_sentence_to_a_player_program(sd, monkeypatch):
    """A device that will not open is a device that is not there: the sentence is
    said by the program player instead, not dropped."""
    _hang_the_open(sd, monkeypatch)
    events: list[str] = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: ProgramUtterance(events),
        on_device_error=lambda error: None,
    )

    utterance.play(timeout=5)

    SlowOpenStream.release.set()
    pcm_player.wait_for_streams_to_close(2)

    assert events == ["played"]


def test_a_healthy_open_is_not_given_up_on(sd, monkeypatch):
    """The deadline is a guard, not a budget: an ordinary open returns at once."""
    monkeypatch.setattr(pcm_player, "STREAM_OPEN_TIMEOUT_SECONDS", 5)

    PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 256)])).play(timeout=5)

    assert not pcm_player.has_open_streams()
