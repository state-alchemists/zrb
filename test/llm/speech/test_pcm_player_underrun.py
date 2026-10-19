"""`PcmUtterance` and the stutter the listener hears: what a device not fed
in time is counted as (`underruns`), the prebuffer keeping the first block
from silence, and a device PortAudio stops mid-sentence."""

import threading
import time
import types
from unittest.mock import patch

import pytest

from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.pcm_player import PcmUtterance

from .test_pcm_player import (
    CallbackStop,
    FakeOutputStream,
    ProgramUtterance,
    RATE,
    _pcm,
    _played,
)

np = pytest.importorskip("numpy")


class UnderrunningOutputStream(FakeOutputStream):
    """A stream whose device says, as PortAudio does, that its block did not
    arrive in time."""

    def _run(self):
        while self._running:
            out = np.zeros((self.blocksize, 1), np.int16)
            flags = types.SimpleNamespace(
                input_underflow=False,
                input_overflow=False,
                output_underflow=True,
                output_overflow=False,
            )
            self.callback(out, self.blocksize, None, flags)
            self.played.append(out.copy())
            time.sleep(0.001)
        self.finished()


class GoneOutputStream(FakeOutputStream):
    """A stream whose device PortAudio stopped as it went (a headset came
    off): never active, no block asked for, and nothing reporting it done."""

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        self.is_closed = True


class StreamGoneMidway(FakeOutputStream):
    """A stream whose device went while it was playing: no block is asked for
    past the last one, and nothing reports it finished."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blocks = 0

    @property
    def active(self) -> bool:
        return self._running and self.blocks < 3

    def _run(self):
        while self._running and self.blocks < 3:
            out = np.zeros((self.blocksize, 1), np.int16)
            try:
                self.callback(out, self.blocksize, None, None)
            except CallbackStop:
                break
            self.played.append(out.copy())
            self.blocks += 1
            time.sleep(0.001)
        # The device is gone: the stream stops without its own `finished`.


@pytest.fixture
def sd():
    FakeOutputStream.instances = []
    fake = types.SimpleNamespace(
        OutputStream=FakeOutputStream, CallbackStop=CallbackStop
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        yield fake


def test_a_block_the_device_says_it_got_early_counts_as_an_underrun(sd, caplog):
    sd.OutputStream = UnderrunningOutputStream
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([5] * 2048)]))

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert stream.played and utterance.underruns >= len(stream.played) - 1
    assert caplog.text.count("stuttered") == 1  # said once, not per block


def test_audio_arriving_too_late_is_counted_as_an_underrun(sd, caplog):
    """Without PortAudio's word on it (its callback produced silence in time),
    a block waiting for the download is what the listener heard as stutter."""

    def arrives_in_drips():
        yield _pcm([5] * 1600)
        time.sleep(0.2)  # the read ahead did not cover this long
        yield _pcm([5] * 1600)

    utterance = PcmUtterance(SpeechAudio(RATE, arrives_in_drips()))

    utterance.play(timeout=5)

    assert utterance.underruns >= 1
    assert "stuttered" in caplog.text


def test_the_first_block_waits_for_the_audio_it_will_play(sd):
    """The device starts on audio in hand, not on silence: a download that
    takes a while does not begin what is said with an empty block."""

    def arrives_late():
        time.sleep(0.2)
        yield _pcm([5] * 1600)

    utterance = PcmUtterance(SpeechAudio(RATE, arrives_late()))

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    played = _played(stream)
    assert played[:1600].tolist() == [5] * 1600
    assert int(np.count_nonzero(played)) == 1600  # nothing lost, nothing fed in late


def test_a_stop_while_the_prebuffer_waits_never_starts_the_device(sd):
    """Stopping what is held still must not make the device speak."""

    def arrives_late():
        time.sleep(0.2)
        yield _pcm([5] * 1024)

    utterance = PcmUtterance(SpeechAudio(RATE, arrives_late()))
    threading.Timer(0.05, utterance.stop).start()

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert stream.played == []
    assert stream.is_closed
    assert utterance.is_stopped


def test_a_device_that_stops_before_its_audio_plays_hands_it_to_a_program(
    sd, caplog
):
    closed = []
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([5] * 1600)], lambda: closed.append(True)),
        fallback=lambda: ProgramUtterance(events),
    )
    sd.OutputStream = GoneOutputStream

    utterance.play(timeout=2)

    assert events == ["played", "cleaned"]
    utterance.cleanup()
    assert closed  # the in-process source is released once played out
    assert "audio device" in caplog.text


def test_a_device_gone_mid_sentence_is_played_as_far_as_it_came(sd, caplog):
    """What was heard was heard, and what came afterwards goes to the next
    sentence's own opening of the device; nothing raises into the caller."""

    def endless():
        while True:
            yield _pcm([5] * 256)

    utterance = PcmUtterance(SpeechAudio(RATE, endless()))
    sd.OutputStream = StreamGoneMidway

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert stream.is_closed
    assert int(np.count_nonzero(_played(stream))) > 0
    assert utterance.is_pausable  # nothing took over to stop it
    assert "cut off" in caplog.text and "audio device" in caplog.text
