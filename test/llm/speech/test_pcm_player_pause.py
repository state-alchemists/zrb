"""`PcmUtterance` held by a pause: the place is held with silence, paused time
is not the utterance's time, and a player program cannot hold at all."""

import threading
import time
import types
from unittest.mock import patch

import pytest

from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.pcm_player import PcmUtterance

from .test_pcm_player import (
    RATE,
    CallbackStop,
    FakeOutputStream,
    ProgramUtterance,
    _broken_device,
    _pcm,
    _played,
)

np = pytest.importorskip("numpy")


@pytest.fixture
def sd():
    FakeOutputStream.instances = []
    fake = types.SimpleNamespace(
        OutputStream=FakeOutputStream, CallbackStop=CallbackStop
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        yield fake


def _resume_once_the_device_plays(utterance, hold: float = 0.0) -> None:
    """Resume *utterance* once the device is playing it, after *hold* more
    seconds of pause.

    Evidence, not a timer: a 50 ms timer races the play loop's start on a
    loaded machine, and the pause it then releases has written nothing — which
    is what the test asserts about, so it fails for a reason that says nothing
    about the player.
    """
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        streams = FakeOutputStream.instances
        if streams and streams[0].played:
            break
        time.sleep(0.001)
    time.sleep(hold)
    utterance.resume()


def test_a_paused_utterance_plays_silence_and_holds_its_place(sd):
    chunks = [_pcm([5] * 1024)] * 3
    utterance = PcmUtterance(SpeechAudio(RATE, chunks))
    utterance.pause()
    assert utterance.is_paused and utterance.is_pausable
    threading.Thread(
        target=_resume_once_the_device_plays, args=(utterance,), daemon=True
    ).start()

    utterance.play(timeout=5)

    played = _played(FakeOutputStream.instances[0])
    first_sound = int(np.argmax(played != 0))
    assert first_sound >= 1024  # silence while paused
    assert int(np.count_nonzero(played)) == 3 * 1024  # nothing skipped


def test_paused_time_does_not_use_up_the_timeout(sd):
    """A user talking over zrb for longer than the timeout must not end the
    sentence they paused: only playing time counts."""
    chunks = [_pcm([5] * 256)] * 2
    utterance = PcmUtterance(SpeechAudio(RATE, chunks))
    utterance.pause()
    threading.Thread(
        target=_resume_once_the_device_plays,
        args=(utterance,),
        kwargs={"hold": 0.3},
        daemon=True,
    ).start()

    utterance.play(timeout=0.2)

    assert not utterance.is_stopped
    assert int(np.count_nonzero(_played(FakeOutputStream.instances[0]))) == 512


def test_a_fallback_paused_before_it_starts_is_not_played():
    """A program cannot hold speech: one paused before it starts would play
    over the user, so it is dropped."""
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: utterance.pause() or ProgramUtterance(events),
    )
    with patch.dict("sys.modules", {"sounddevice": _broken_device()}):
        utterance.play(timeout=1)

    assert events == ["cleaned"]


def test_a_fallback_held_by_a_pause_reports_no_start():
    started = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: utterance.pause() or ProgramUtterance([]),
    )
    utterance.set_on_start(lambda: started.append(True))
    with patch.dict("sys.modules", {"sounddevice": _broken_device()}):
        utterance.play(timeout=1)

    assert started == []


def test_a_finished_fallback_no_longer_counts_as_playing():
    """Once the player program is done, a pause holds the utterance again
    instead of stopping a program that has already exited."""
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: ProgramUtterance(events),
    )
    with patch.dict("sys.modules", {"sounddevice": _broken_device()}):
        utterance.play(timeout=1)

    assert utterance.is_pausable
    utterance.pause()
    assert "stopped" not in events
