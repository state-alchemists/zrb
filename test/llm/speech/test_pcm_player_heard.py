"""`SpeechAudio.on_block`: what is heard, in the order it is heard, and once
at the end — the signal a mouth or a caption has to follow, where reading the
chunks runs seconds ahead of it."""

import types
from unittest.mock import patch

import pytest

from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.pcm_player import PcmUtterance

from .test_pcm_player import RATE, CallbackStop, FakeOutputStream, _pcm, _played

np = pytest.importorskip("numpy")


@pytest.fixture
def sd():
    FakeOutputStream.instances = []
    fake = types.SimpleNamespace(
        OutputStream=FakeOutputStream, CallbackStop=CallbackStop
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        yield fake


def _utterance(chunks, heard):
    return PcmUtterance(SpeechAudio(RATE, chunks, on_block=heard.append))


def test_each_block_is_reported_as_the_device_takes_it(sd):
    """What the listener is told is the audio the device is playing, not the
    audio the reader has already downloaded."""
    samples = list(range(1, 2049))
    heard = []
    utterance = _utterance([_pcm(samples[:700]), _pcm(samples[700:])], heard)

    assert heard == []  # created, still nothing heard
    utterance.play(timeout=5)

    assert b"".join(block for block in heard if block) == _pcm(samples)


def test_the_end_is_reported_once_and_last(sd):
    heard = []
    _utterance([_pcm([1] * 256)], heard).play(timeout=5)

    assert heard[-1] == b""
    assert heard.count(b"") == 1  # the callback keeps running after it ends


def test_a_listener_that_raises_does_not_silence_the_sentence(sd):
    samples = list(range(1, 2049))

    def broken(block):
        raise RuntimeError("the listener's bug")

    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm(samples[:700]), _pcm(samples[700:])], on_block=broken)
    )
    utterance.play(timeout=5)  # it runs on the audio thread: it may not raise

    [stream] = FakeOutputStream.instances
    assert _played(stream)[: len(samples)].tolist() == samples


def test_no_audio_means_nothing_to_report(sd):
    """A sentence that played nothing -- the fallback took it, or the device
    never got it -- says nothing rather than announcing an end it never had."""
    heard = []
    PcmUtterance(SpeechAudio(RATE, [])).play(timeout=5)
    PcmUtterance(SpeechAudio(RATE, [], on_block=heard.append))
    assert heard == []


def test_the_listener_hears_the_samples_the_device_plays(sd):
    """After volume and clipping, not the samples as they were read."""
    heard = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1000, -1000, 30000] * 100)], on_block=heard.append),
        volume=50,
    )
    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    played = _played(stream)[:300].tolist()
    assert played[:3] == [500, -500, 15000]
    assert b"".join(block for block in heard if block) == _pcm(played)


def test_stopping_before_play_still_reports_the_end(sd):
    heard = []
    utterance = _utterance([_pcm([1] * 256)], heard)
    utterance.stop()
    utterance.play(timeout=5)

    assert heard == [b""]
