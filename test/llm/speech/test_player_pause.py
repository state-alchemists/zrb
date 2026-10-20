"""Pin pause, resume, and what a pause holds or drops."""

import threading
import time

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance


class RecordingUtterance(Utterance):
    def __init__(self, text, played, done):
        super().__init__([])
        self.text, self.played, self.done = text, played, done

    def play(self, timeout):
        self.report_started()
        self.played.append(self.text)
        self.done.set()


class FakeBackend(AnySpeechBackend):
    def __init__(self):
        self.played: list[str] = []

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played, threading.Event())


class HangingUtterance(Utterance):
    """An utterance that plays until stopped."""

    def __init__(self, started):
        super().__init__([])
        self.started = started
        self.stopped = threading.Event()

    def play(self, timeout):
        self.report_started()
        self.started.set()
        self.stopped.wait(5)

    def stop(self):
        self.stopped.set()


class HangingBackend(AnySpeechBackend):
    def __init__(self):
        self.started = threading.Event()
        self.utterances: list = []

    def create_utterance(self, text):
        utterance = HangingUtterance(self.started)
        self.utterances.append(utterance)
        return utterance


class SignallingBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.done = threading.Event()

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played, self.done)


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file, **fields):
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


class PausableUtterance(HangingUtterance):
    def __init__(self, started):
        super().__init__(started)
        self.events: list[str] = []

    @property
    def is_pausable(self):
        return True

    def pause(self):
        self.events.append("pause")

    def resume(self):
        self.events.append("resume")


def _slow_backend(created, release):
    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            created.set()
            release.wait(5)
            return super().create_utterance(text)

    return SlowBackend()


def test_pause_holds_a_pausable_utterance_and_resume_carries_on(lock_file):
    backend = HangingBackend()
    backend.create_utterance = (
        lambda text: backend.utterances.append(PausableUtterance(backend.started))
        or backend.utterances[-1]
    )
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("long")
    assert backend.started.wait(5)

    speaker.pause()
    speaker.resume()

    assert backend.utterances[0].events == ["pause", "resume"]
    speaker.close()


def test_pause_stops_only_the_sentence_that_cannot_pause(lock_file):
    """A player program cannot hold, so its sentence stops; what follows is
    held, not dropped, so a false alarm resumes with the next sentence."""
    started, release = threading.Event(), threading.Event()
    played: list[str] = []

    class Backend(AnySpeechBackend):
        def create_utterance(self, text):
            if text == "first":
                return HangingUtterance(started)
            return RecordingUtterance(text, played, release)

    speaker = Speaker(_config(Backend(), lock_file))
    speaker.resume()
    speaker.say("first")
    speaker.say("second")
    assert started.wait(5)

    speaker.pause()
    assert not release.wait(0.3)

    speaker.resume()
    assert release.wait(5)
    assert played == ["second"]
    speaker.close()


@pytest.mark.parametrize("switch_off", [True, False])
def test_speech_being_made_when_cleared_is_never_played(lock_file, switch_off):
    """Clearing or disabling speech drops a sentence still being synthesized."""
    created, release = threading.Event(), threading.Event()
    backend = _slow_backend(created, release)
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("in the making")
    assert created.wait(5)

    if switch_off:
        speaker.is_enabled = False
    speaker.clear()
    release.set()
    speaker.drain()

    assert backend.played == []


def test_speech_made_while_paused_waits_for_resume(lock_file):
    backend = SignallingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()

    speaker.say("queued")
    assert not backend.done.wait(0.3)

    speaker.resume()
    assert backend.done.wait(5)
    assert backend.played == ["queued"]
    speaker.close()


def test_interrupting_a_pause_drops_what_waited_and_unpauses(lock_file):
    backend = SignallingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()
    speaker.say("dropped")
    assert not backend.done.wait(0.3)

    speaker.interrupt()
    speaker.say("next")

    assert backend.done.wait(5)
    assert backend.played == ["next"]
    speaker.close()


def test_closing_a_paused_speaker_does_not_hang(lock_file):
    backend = SignallingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()
    speaker.say("never")
    speaker.close()
    assert not backend.done.wait(0.3)
    assert backend.played == []


def test_drain_does_not_wait_for_speech_a_pause_holds(lock_file):
    backend = SignallingBackend()
    config = SpeechConfig(
        backend=backend,
        lock_file=lock_file,
        lock_timeout=0.05,
        player="command",
        drain_timeout=5,
    ).resolve()
    speaker = Speaker(config)
    speaker.pause()
    speaker.say("held")

    started = time.monotonic()
    speaker.drain()

    assert time.monotonic() - started < 2
    assert backend.played == []
