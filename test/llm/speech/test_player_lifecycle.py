"""`Speaker`: what its end leaves behind, and what it must not.

Queueing, ordering and interruption are `test_player.py`; what an ended speaker
still owes — releasing the backends it made, speaking nothing more, and being
forgotten by the lock-file registry — is here. Like its siblings, it carries its
own copy of the fixtures: a test file is a feature group, not a library.
"""

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
    # Played by a program unless a test says otherwise: these tests are about
    # what an ended speaker does, not where the audio goes.
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


def test_a_closed_speaker_stops_being_probed_for_its_lock_file(lock_file):
    """`is_speaking` probes every lock file a live speaker configured, once
    per captured audio block. A speaker that has gone away must stop being
    one, or a long-lived process keeps re-checking a dead session's path and
    stays muted whenever anything else holds it."""
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
    """A backend still synthesizing when the session closes."""
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
    """Both ways a speaker ends release the backends, thread or no thread.

    `speak` plays on the calling thread and never starts the worker and player
    threads, but it makes the same backends `say` does — a Pipecat service is a
    model and a pipeline whoever asked for it. Stopping on the thread's absence
    left all of that, and the loop and thread under it, for the life of the
    process: `close` for a session that is over, `drain` for the exit of one that
    never called it.
    """
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
