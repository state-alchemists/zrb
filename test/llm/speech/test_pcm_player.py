"""`PcmUtterance`: speech played in process, through a fake sounddevice
whose output stream calls back on a thread, as PortAudio does."""

import threading
import time
import types
from unittest.mock import patch

import pytest

from zrb.llm.speech import pcm_player
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.pcm_player import PcmUtterance

RATE = 16000

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

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if getattr(self, "_thread", None) is not None:
            self._thread.join(1)

    def close(self):
        self.is_closed = True

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


def test_the_start_is_reported_once_the_device_plays(sd):
    started = []
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([1] * 256)]))
    utterance.set_on_start(lambda: started.append(len(FakeOutputStream.instances)))

    utterance.play(timeout=5)

    assert started == [1]


def test_the_audio_is_played(sd):
    samples = list(range(1, 2049))
    chunks = [_pcm(samples[:700]), _pcm(samples[700:])]
    utterance = PcmUtterance(SpeechAudio(RATE, chunks))

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert _played(stream)[:2048].tolist() == samples


def test_a_paused_utterance_plays_silence_and_holds_its_place(sd):
    chunks = [_pcm([5] * 1024)] * 3
    utterance = PcmUtterance(SpeechAudio(RATE, chunks))
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

    utterance = PcmUtterance(SpeechAudio(RATE, endless(), lambda: closed.append(True)))
    threading.Timer(0.05, utterance.stop).start()

    utterance.play(timeout=5)

    assert utterance.is_stopped and closed


def test_the_timeout_stops_an_utterance_that_never_ends(sd):
    def endless():
        while True:
            yield _pcm([1] * 256)

    utterance = PcmUtterance(SpeechAudio(RATE, endless()))
    utterance.play(timeout=0.05)
    assert utterance.is_stopped


def test_a_stopped_utterance_does_not_play(sd):
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([1])]))
    utterance.stop()
    utterance.play(timeout=1)
    assert FakeOutputStream.instances == []


def test_a_failing_download_plays_what_came(sd):
    def failing():
        yield _pcm([7] * 100)
        raise OSError("connection reset")

    utterance = PcmUtterance(SpeechAudio(RATE, failing()))
    utterance.play(timeout=5)
    assert int(np.count_nonzero(_played(FakeOutputStream.instances[0]))) == 100
    utterance.cleanup()


def test_is_available_says_whether_the_audio_packages_import():
    pcm_player.is_available.cache_clear()
    try:
        with patch.dict("sys.modules", {"sounddevice": None}):
            assert pcm_player.is_available() is False
        pcm_player.is_available.cache_clear()
        with patch.dict("sys.modules", {"sounddevice": types.SimpleNamespace()}):
            assert pcm_player.is_available() is True
    finally:
        pcm_player.is_available.cache_clear()


@pytest.mark.parametrize("fails_on", ["open", "start"])
def test_a_device_that_fails_closes_the_source_and_reads_nothing(monkeypatch, fails_on):
    opened = []

    class BrokenStream(FakeOutputStream):
        def __init__(self, *args, **kwargs):
            if fails_on == "open":
                raise OSError("no default output device")
            super().__init__(*args, **kwargs)
            opened.append(self)

        def start(self):
            raise OSError("device busy")

    read = []

    def chunks():
        read.append(True)
        yield _pcm([1] * 256)

    closed = []
    fake = types.SimpleNamespace(OutputStream=BrokenStream, CallbackStop=CallbackStop)
    utterance = PcmUtterance(SpeechAudio(RATE, chunks(), lambda: closed.append(True)))
    with patch.dict("sys.modules", {"sounddevice": fake}):
        with pytest.raises(OSError):
            utterance.play(timeout=1)

    assert closed
    if fails_on == "open":
        assert read == []  # the reader never started
    else:
        # Opened but never started: closed all the same, not leaked.
        assert [stream.is_closed for stream in opened] == [True]


class ProgramUtterance(Utterance):
    """Stands in for a player program's utterance."""

    def __init__(self, events):
        super().__init__([])
        self.events = events

    def play(self, timeout):
        self.report_started()
        self.events.append("played")

    def stop(self):
        self.events.append("stopped")

    def cleanup(self):
        self.events.append("cleaned")


def _broken_device(fails_on="open", after_opening=False):
    class BrokenStream(FakeOutputStream):
        def __init__(self, *args, **kwargs):
            if fails_on == "open":
                raise OSError("no default output device")
            super().__init__(*args, **kwargs)

        def start(self):
            if after_opening:
                return super().start()
            raise OSError("device busy")

        def stop(self):
            super().stop()
            if after_opening:
                raise OSError("device lost")

    return types.SimpleNamespace(OutputStream=BrokenStream, CallbackStop=CallbackStop)


@pytest.mark.parametrize("fails_on", ["open", "start"])
def test_a_device_that_cannot_open_hands_the_speech_to_a_player_program(fails_on):
    events, closed = [], []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)], lambda: closed.append(True)),
        fallback=lambda: ProgramUtterance(events),
    )
    with patch.dict("sys.modules", {"sounddevice": _broken_device(fails_on)}):
        utterance.play(timeout=1)

    assert events == ["played", "cleaned"]
    assert closed  # the in-process source is released


def test_a_device_failing_after_it_opened_is_not_played_twice():
    events = []
    device = _broken_device("start", after_opening=True)
    fresh = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: ProgramUtterance(events),
    )
    with patch.dict("sys.modules", {"sounddevice": device}):
        with pytest.raises(OSError, match="device lost"):
            fresh.play(timeout=0.05)

    assert events == []


def test_stopping_during_the_fallback_stops_the_player_program():
    events = []
    started = threading.Event()

    class Hanging(ProgramUtterance):
        def play(self, timeout):
            started.set()
            time.sleep(0.2)

    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: Hanging(events),
    )
    with patch.dict("sys.modules", {"sounddevice": _broken_device()}):
        player = threading.Thread(target=utterance.play, args=(1,))
        player.start()
        assert started.wait(5)
        assert not utterance.is_pausable  # a program cannot pause
        utterance.stop()
        player.join(1)

    assert "stopped" in events


def _failing_source(chunks_first=()):
    def chunks():
        yield from chunks_first
        raise ConnectionError("connection reset")

    return chunks()


def test_audio_failing_before_any_of_it_played_goes_to_the_player_program(sd):
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, _failing_source()),
        fallback=lambda: ProgramUtterance(events),
    )

    utterance.play(timeout=5)

    assert events == ["played", "cleaned"]


def test_audio_failing_part_way_is_played_as_far_as_it_came_and_logged(sd, caplog):
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, _failing_source([_pcm([7] * 512)])),
        fallback=lambda: ProgramUtterance(events),
    )

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert _played(stream)[:512].tolist() == [7] * 512
    assert events == []  # replaying it would say the start twice
    assert "cut off" in caplog.text and "connection reset" in caplog.text


def test_audio_cut_off_by_stop_is_no_failure(sd, caplog):
    events = []

    def chunks():
        yield _pcm([1] * 256)
        utterance.stop()
        raise ConnectionError("closed by stop")

    utterance = PcmUtterance(
        SpeechAudio(RATE, chunks()),
        fallback=lambda: ProgramUtterance(events),
    )

    utterance.play(timeout=5)

    assert events == []
    assert "closed by stop" not in caplog.text


def test_paused_time_does_not_use_up_the_timeout(sd):
    """A user talking over zrb for longer than the timeout must not end the
    sentence they paused: only playing time counts."""
    chunks = [_pcm([5] * 256)] * 2
    utterance = PcmUtterance(SpeechAudio(RATE, chunks))
    utterance.pause()
    threading.Timer(0.3, utterance.resume).start()

    utterance.play(timeout=0.2)

    assert not utterance.is_stopped
    assert int(np.count_nonzero(_played(FakeOutputStream.instances[0]))) == 512


class TimedProgramUtterance(ProgramUtterance):
    def play(self, timeout):
        self.events.append(("played", timeout))


def test_the_fallback_after_failing_audio_keeps_the_timeout(sd):
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, _failing_source()),
        fallback=lambda: TimedProgramUtterance(events),
    )

    utterance.play(timeout=7)

    assert ("played", 7) in events


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


def test_a_device_that_cannot_open_reports_the_start_of_the_player_program():
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([1] * 256)]),
        fallback=lambda: ProgramUtterance(events),
    )
    utterance.set_on_start(lambda: events.append("started"))
    with patch.dict("sys.modules", {"sounddevice": _broken_device()}):
        utterance.play(timeout=1)

    assert events == ["started", "played", "cleaned"]


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
