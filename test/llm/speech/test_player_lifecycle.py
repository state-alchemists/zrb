"""Pin Speaker cleanup, silence after close, and lock-file deregistration."""

import threading
import time

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.player import is_speaking
from zrb.util.file_lock import hold_file_lock


class RecordingUtterance(Utterance):
    def __init__(self, text, played, done):
        super().__init__([])
        self.text = text
        self.played = played
        self.done = done
        self.cleaned = False

    def play(self, timeout):
        self.played.append(self.text)
        self.done.set()

    def cleanup(self):
        self.cleaned = True


class FakeBackend(AnySpeechBackend):
    def __init__(self):
        self.played: list[str] = []
        self.done = threading.Event()
        self.utterances: list[RecordingUtterance] = []

    def create_utterance(self, text):
        utterance = RecordingUtterance(text, self.played, self.done)
        self.utterances.append(utterance)
        return utterance


class ClosingBackend(FakeBackend):
    """A backend that says when the speaker let it go."""

    def __init__(self):
        super().__init__()
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file, **fields):
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


def test_a_closed_speaker_stops_being_probed_for_its_lock_file(lock_file):
    """A closed speaker is no longer reported by its lock file."""
    Speaker(_config(FakeBackend(), lock_file)).close()

    with hold_file_lock(lock_file):
        assert not is_speaking()


def test_a_closed_speaker_says_nothing(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.close()

    speaker.say("too late")
    speaker.drain()

    assert backend.played == []


def test_speech_created_after_close_is_never_played(lock_file):
    """Speech created after close is cleaned up without playback."""
    created = threading.Event()
    release = threading.Event()

    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            created.set()
            release.wait(5)
            return super().create_utterance(text)

    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("slow")
    assert created.wait(1)

    speaker.close()
    release.set()
    time.sleep(0.1)

    assert backend.played == []
    assert backend.utterances[0].cleaned


def test_text_said_later_is_dropped_when_the_speaker_closes(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    producing = threading.Event()
    release = threading.Event()

    def produce():
        producing.set()
        release.wait(5)
        return "too late"

    speaker.say_later(produce)
    assert producing.wait(1)
    speaker.close()
    release.set()
    time.sleep(0.1)

    assert backend.played == []


def test_a_backend_is_let_go_when_speech_never_started_a_thread(lock_file):
    """Close and drain release backends even without worker threads."""
    spoken = ClosingBackend()
    speaker = Speaker(_config(spoken, lock_file))
    drained = ClosingBackend()
    draining = Speaker(_config(drained, lock_file))

    speaker.speak("one")
    speaker.close()
    draining.speak("two")
    draining.drain()

    assert spoken.played == ["one"]
    assert drained.played == ["two"]
    assert spoken.closed
    assert drained.closed


def test_a_backend_still_synthesizing_at_close_is_let_go_only_after(lock_file):
    created = threading.Event()
    release = threading.Event()
    closed_while_synthesizing = []

    class SlowClosingBackend(ClosingBackend):
        def create_utterance(self, text):
            created.set()
            release.wait(5)
            closed_while_synthesizing.append(self.closed)
            return super().create_utterance(text)

    backend = SlowClosingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("slow")
    assert created.wait(1)

    speaker.close()
    release.set()
    time.sleep(0.1)

    assert closed_while_synthesizing == [False]
    assert backend.closed
    assert backend.utterances[0].cleaned


def test_a_backend_is_not_let_go_while_its_last_sentence_is_still_playing(lock_file):
    """A backend remains until the player finishes its final sentence."""
    let_go_while_playing: "list[bool]" = []
    let_go = threading.Event()

    class PlayingUtterance(RecordingUtterance):
        """An utterance held until released."""

        def __init__(self, text, played, done, playing, release):
            super().__init__(text, played, done)
            self._playing = playing
            self._release = release

        def play(self, timeout):
            self._playing.set()
            self._release.wait(5)
            super().play(timeout)

    class WatchedBackend(ClosingBackend):
        """A backend that records whether it closed during playback."""

        def __init__(self):
            super().__init__()
            self.playing = threading.Event()
            self.release = threading.Event()

        def create_utterance(self, text):
            return PlayingUtterance(
                text, self.played, self.done, self.playing, self.release
            )

        def close(self):
            let_go_while_playing.append(
                self.playing.is_set() and not self.release.is_set()
            )
            super().close()
            let_go.set()

    backend = WatchedBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("the last sentence")
    assert backend.playing.wait(5)

    speaker.close()
    time.sleep(0.3)
    assert let_go_while_playing == []

    backend.release.set()
    assert let_go.wait(5)
    assert let_go_while_playing == [False]
    assert backend.closed
