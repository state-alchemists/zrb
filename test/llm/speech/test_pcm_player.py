"""`PcmUtterance`: speech played in process, through a fake sounddevice
whose output stream calls back on a thread, as PortAudio does."""

import threading
import time
import types
from unittest.mock import patch

import pytest

from zrb.llm.speech import pcm_player
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.echo_reference import RATE, EchoReference
from zrb.llm.speech.pcm_player import PcmUtterance

np = pytest.importorskip("numpy")


class CallbackStop(Exception):
    pass


class FakeOutputStream:
    latency = 0.02
    instances: list = []

    def __init__(
        self, samplerate, channels, dtype, blocksize, callback, finished_callback
    ):
        self.rate, self.blocksize = samplerate, blocksize
        self.callback, self.finished = callback, finished_callback
        self.played: list = []
        self._running = False
        FakeOutputStream.instances.append(self)

    def __enter__(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._running = False
        self._thread.join(1)
        return False

    def _run(self):
        while self._running:
            out = np.zeros((self.blocksize, 1), np.int16)
            try:
                self.callback(out, self.blocksize, None, None)
            except CallbackStop:
                self.played.append(out.copy())
                break
            self.played.append(out.copy())
            time.sleep(0.001)
        self.finished()


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


def _played(stream):
    return np.concatenate(stream.played)[:, 0]


def test_the_audio_is_played_and_written_to_the_echo_reference(sd):
    reference = EchoReference()
    starts = []
    write = reference.write
    reference.write = lambda start, audio: (starts.append(start), write(start, audio))
    samples = list(range(1, 2049))
    chunks = [_pcm(samples[:700]), _pcm(samples[700:])]
    utterance = PcmUtterance(SpeechAudio(RATE, chunks), reference)

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert _played(stream)[:2048].tolist() == samples
    assert not reference.is_active
    heard = reference.read(starts[0], 2048)
    assert np.allclose(heard, np.array(samples) / 32768, atol=1e-6)


def test_the_reference_is_resampled_to_16_khz(sd):
    reference = EchoReference()
    utterance = PcmUtterance(SpeechAudio(24000, [_pcm([1000] * 2400)]), reference)
    writes = []
    reference.write = lambda start, audio: writes.append((start, len(audio)))

    utterance.play(timeout=5)

    total = sum(length for _, length in writes)
    assert abs(total - 1600) <= len(writes)  # 2400 samples at 24 kHz = 0.1 s
    starts = [start for start, _ in writes]
    assert starts == sorted(starts)


def test_a_paused_utterance_plays_silence_and_holds_its_place(sd):
    reference = EchoReference()
    chunks = [_pcm([5] * 1024)] * 3
    utterance = PcmUtterance(SpeechAudio(RATE, chunks), reference)
    utterance.pause()
    assert utterance.is_paused and utterance.is_pausable
    threading.Timer(0.05, utterance.resume).start()

    utterance.play(timeout=5)

    played = _played(FakeOutputStream.instances[0])
    first_sound = int(np.argmax(played != 0))
    assert first_sound >= 1024  # silence while paused
    assert int(np.count_nonzero(played)) == 3 * 1024  # nothing skipped


def test_stop_ends_playback_and_closes_the_download(sd):
    closed = []

    def endless():
        while True:
            yield _pcm([1] * 256)

    utterance = PcmUtterance(
        SpeechAudio(RATE, endless(), lambda: closed.append(True)), EchoReference()
    )
    threading.Timer(0.05, utterance.stop).start()

    utterance.play(timeout=5)

    assert utterance.is_stopped and closed


def test_the_timeout_stops_an_utterance_that_never_ends(sd):
    def endless():
        while True:
            yield _pcm([1] * 256)

    utterance = PcmUtterance(SpeechAudio(RATE, endless()), EchoReference())
    utterance.play(timeout=0.05)
    assert utterance.is_stopped


def test_a_stopped_utterance_does_not_play(sd):
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([1])]), EchoReference())
    utterance.stop()
    utterance.play(timeout=1)
    assert FakeOutputStream.instances == []


def test_a_failing_download_plays_what_came(sd):
    def failing():
        yield _pcm([7] * 100)
        raise OSError("connection reset")

    utterance = PcmUtterance(SpeechAudio(RATE, failing()), EchoReference())
    utterance.play(timeout=5)
    assert int(np.count_nonzero(_played(FakeOutputStream.instances[0]))) == 100
    utterance.cleanup()


def test_is_available_says_whether_the_audio_packages_import(monkeypatch):
    monkeypatch.setattr(pcm_player, "_available", None)
    with patch.dict("sys.modules", {"sounddevice": None}):
        assert pcm_player.is_available() is False
    monkeypatch.setattr(pcm_player, "_available", None)
    with patch.dict("sys.modules", {"sounddevice": types.SimpleNamespace()}):
        assert pcm_player.is_available() is True


@pytest.mark.parametrize("fails_on", ["open", "start"])
def test_a_device_that_fails_closes_the_source_and_reads_nothing(monkeypatch, fails_on):
    class BrokenStream(FakeOutputStream):
        def __init__(self, *args, **kwargs):
            if fails_on == "open":
                raise OSError("no default output device")
            super().__init__(*args, **kwargs)

        def __enter__(self):
            raise OSError("device busy")

    read = []

    def chunks():
        read.append(True)
        yield _pcm([1] * 256)

    closed = []
    fake = types.SimpleNamespace(OutputStream=BrokenStream, CallbackStop=CallbackStop)
    utterance = PcmUtterance(
        SpeechAudio(RATE, chunks(), lambda: closed.append(True)), EchoReference()
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        with pytest.raises(OSError):
            utterance.play(timeout=1)

    assert closed and utterance.is_stopped
    if fails_on == "open":
        assert read == []  # the reader never started
