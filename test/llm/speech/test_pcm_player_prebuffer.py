"""`ZRB_LLM_SPEECH_PLAYER_PREBUFFER_SECONDS`: how much audio the device starts
on, why the wait that holds it off has to grow with it, and what the cushion
buys — a stall in the engine that is absorbed instead of heard."""

import time
import types
from dataclasses import fields
from unittest.mock import patch

import pytest

from zrb.config.config import CFG
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.pcm_player import PcmUtterance, prebuffer_wait_seconds

from .test_pcm_player import (
    RATE,
    CallbackStop,
    FakeOutputStream,
    ProgramUtterance,
    _pcm,
    _played,
)
from .test_pcm_player_underrun import GoneOutputStream

np = pytest.importorskip("numpy")

# One block of the player's default size, and how long it plays for.
BLOCK = 1024
BLOCK_SECONDS = BLOCK / RATE
# A stall long enough to be heard, and clear of the sleeps' own jitter.
STALL_SECONDS = 0.4


class TimedStream(FakeOutputStream):
    """A stream that says when its device started playing."""

    def start(self):
        self.started_at = time.monotonic()
        super().start()


class RealtimeStream(FakeOutputStream):
    """A device that asks for the next block once the last one would have
    played, so a source keeping up is heard without stutter."""

    def _run(self):
        while self._running:
            out = np.zeros((self.blocksize, 1), np.int16)
            self.callback(out, self.blocksize, None, None)
            self.played.append(out.copy())
            time.sleep(BLOCK_SECONDS)
        self.finished()


def _pausing_source(pause=STALL_SECONDS):
    """Audio that arrives, pauses, then arrives again: a render that stalled."""

    def chunks():
        yield _pcm([5] * 1600)
        time.sleep(pause)
        yield _pcm([5] * 1600)

    return chunks()


def _stalling_source(stall=STALL_SECONDS):
    """Audio produced just faster than it plays, with one stall in the middle.

    Faster than playback on purpose: the stall is then the only reason the
    device could go unfed, which is what the cushion is for.
    """

    def chunks():
        for index in range(15):
            if index == 3:
                time.sleep(stall)
            time.sleep(BLOCK_SECONDS * 0.85)
            yield _pcm([5] * BLOCK)

    return chunks()


def _start_delay(prebuffer_seconds):
    """How long `play` held the device off, in seconds."""
    FakeOutputStream.instances = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, _pausing_source()), prebuffer_seconds=prebuffer_seconds
    )
    started = time.monotonic()
    utterance.play(timeout=15)
    [stream] = FakeOutputStream.instances
    return stream.started_at - started


@pytest.fixture
def sd():
    FakeOutputStream.instances = []
    fake = types.SimpleNamespace(
        OutputStream=FakeOutputStream, CallbackStop=CallbackStop
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        yield fake


def test_the_wait_grows_with_the_cushion():
    """A cushion longer than the old flat second must not be capped back to
    it: the wait is what the cushion has to be delivered inside."""
    assert prebuffer_wait_seconds(0.1) == 1.0
    assert prebuffer_wait_seconds(0.4) == 1.0
    assert prebuffer_wait_seconds(0.6) == pytest.approx(1.2)
    assert prebuffer_wait_seconds(3.0) == pytest.approx(6.0)
    for cushion in (0.05, 0.1, 0.4, 0.6, 1.0, 5.0):
        assert prebuffer_wait_seconds(cushion) >= cushion


def test_the_device_starts_on_the_audio_the_cushion_asks_for(sd):
    """The cushion decides how much audio stands by: a tenth of a second
    starts on the first chunk, half a second waits the source's pause out."""
    sd.OutputStream = TimedStream

    thin = _start_delay(0.1)
    deep = _start_delay(0.5)

    assert thin < STALL_SECONDS / 2  # started before the pause was over
    assert deep >= STALL_SECONDS / 2  # held until it was


def test_the_cushion_is_read_from_the_configuration_when_none_is_given(sd, monkeypatch):
    """Left unset, the player takes the configured cushion rather than a
    constant of its own, so the setting reaches the device that plays."""
    monkeypatch.setattr(CFG, "LLM_SPEECH_PLAYER_PREBUFFER_SECONDS", 0.5)
    sd.OutputStream = TimedStream

    utterance = PcmUtterance(SpeechAudio(RATE, _pausing_source()))
    started = time.monotonic()
    utterance.play(timeout=15)

    [stream] = FakeOutputStream.instances
    assert stream.started_at - started >= STALL_SECONDS / 2


def test_a_zero_cushion_still_waits_for_the_first_audio(sd):
    """`0` starts on whatever has arrived, which is not the same as starting on
    nothing: a device fed an empty first block opens the sentence on silence."""

    def arrives_late():
        time.sleep(0.2)
        yield _pcm([5] * 1600)
        yield _pcm([5] * 1600)

    sd.OutputStream = TimedStream
    utterance = PcmUtterance(SpeechAudio(RATE, arrives_late()), prebuffer_seconds=0.0)
    started = time.monotonic()
    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert stream.started_at - started >= 0.15  # waited for the first chunk
    assert _played(stream)[:1600].tolist() == [5] * 1600  # not silence


def test_the_newest_speech_setting_is_the_last_field():
    """A dataclass is positional too: a field added in the middle rebinds every
    field after it for a caller that passes them that way."""
    assert [field.name for field in fields(SpeechConfig)][-1] == (
        "player_prebuffer_seconds"
    )


def test_the_cushion_is_added_last_so_a_positional_caller_still_fits(sd):
    """An older call passing the older options by position keeps meaning what
    it meant: the cushion sits after them, not among them."""
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([5] * 1600)]),
        BLOCK,  # block_frames
        32,  # read_ahead
        lambda: ProgramUtterance(events),  # fallback, the fourth positional
    )
    sd.OutputStream = GoneOutputStream  # a device that cannot play

    utterance.play(timeout=2)

    assert events == ["played", "cleaned"]


def test_the_read_ahead_count_does_not_cap_the_cushion(sd):
    """A cushion counted in seconds cannot be bounded by a count of chunks: a
    backend streaming small ones would never hold it, so the sentence would
    start under its cushion once the wait ran out."""

    def small_chunks():
        for _ in range(200):
            yield _pcm([5] * 160)  # 10 ms of audio per chunk
            time.sleep(0.002)

    sd.OutputStream = TimedStream
    utterance = PcmUtterance(
        SpeechAudio(RATE, small_chunks()), read_ahead=2, prebuffer_seconds=0.4
    )
    started = time.monotonic()
    utterance.play(timeout=15)

    [stream] = FakeOutputStream.instances
    # 0.4 s of audio is 40 such chunks, made well inside the second the wait
    # would have run out at: the device starts on the cushion, not on the wait.
    assert stream.started_at - started < 0.5


def test_a_longer_cushion_absorbs_a_stall_in_the_audio(sd):
    """A stall mid-sentence is what the listener hears as a clipped word; the
    cushion is what decides whether it is heard at all."""
    sd.OutputStream = RealtimeStream

    def underruns_with(prebuffer_seconds):
        utterance = PcmUtterance(
            SpeechAudio(RATE, _stalling_source()),
            prebuffer_seconds=prebuffer_seconds,
        )
        utterance.play(timeout=15)
        return utterance.underruns

    thin = underruns_with(0.1)
    deep = underruns_with(0.4)

    assert thin >= 1  # the stall was heard on the old cushion
    assert deep == 0  # and absorbed on the new one
