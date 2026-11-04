"""A speaker takes turns on one device with the user's other sessions.

Sessions of one user share a lock file, so one of them is always talking at a
time. These tests pin what the waiting side does: wait its turn, say so once,
drop a sentence that stopped mattering, and survive a `drain()` that is waiting
for it.
"""

import logging
import threading
import time

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.player import is_speaking
from zrb.util.file_lock import FileLockTimeout, hold_file_lock


class RecordingUtterance(Utterance):
    def __init__(self, text: str, played: list[str]):
        super().__init__([])
        self.text = text
        self.played = played
        self.cleaned = False

    def play(self, timeout):
        self.played.append(self.text)

    def cleanup(self):
        self.cleaned = True


class FakeBackend(AnySpeechBackend):
    def __init__(self):
        self.played: list[str] = []

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played)


class LogRecorder(logging.Handler):
    """Keeps the lines a speaker logs, so a test can count them."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file, **fields):
    # Played by a program: these tests are about waiting for the device, not
    # about where the audio goes.
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


def _hold_the_device(lock_file: str, seconds: float) -> threading.Thread:
    """Another session holding the device for *seconds*, on a thread of its own."""
    acquired, release = threading.Event(), threading.Event()

    def holder() -> None:
        with hold_file_lock(lock_file):
            acquired.set()
            release.wait(5)

    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    assert acquired.wait(5)
    threading.Timer(seconds, release.set).start()
    return thread


def test_a_synchronous_speak_still_gives_up_on_another_session(lock_file):
    """`speak()` promises `FileLockTimeout`, and keeps it: only the queue waits."""
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    with hold_file_lock(lock_file):
        assert is_speaking(lock_file)
        with pytest.raises(FileLockTimeout):
            speaker.speak("dropped")  # lock_timeout passes while it is held

    assert backend.played == []
    assert not is_speaking(lock_file)


def test_a_queued_sentence_waits_for_the_other_session_and_is_heard(lock_file):
    """Another chat speaking used to cost the sentence: it waited `lock_timeout`
    and was dropped. The lock is whose turn it is, so the sentence waits for its
    turn instead."""
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    with hold_file_lock(lock_file):
        speaker.say("waits")
        # Longer than lock_timeout and long enough for the sentence to have been
        # made and offered to the player: without the wait it is dropped by now.
        time.sleep(0.5)
        assert backend.played == []
    speaker.drain()

    assert backend.played == ["waits"]


def test_a_wait_is_announced_once_and_not_once_a_slice(lock_file):
    """A late reply says so once, however many times it looks at the device."""
    recorder = LogRecorder()
    player_logger = logging.getLogger("zrb.llm.speech.player")
    player_logger.addHandler(recorder)
    try:
        speaker = Speaker(_config(FakeBackend(), lock_file))
        with hold_file_lock(lock_file):
            speaker.say("waits")
            time.sleep(1.0)  # four polls, so four lines if it were not said once
        speaker.drain()
    finally:
        player_logger.removeHandler(recorder)

    assert sum("Speech waits" in text for text in recorder.messages) == 1


def test_a_sentence_interrupted_while_waiting_is_dropped(lock_file):
    """A wait is not a promise: what the wait was for still has to be wanted."""
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    with hold_file_lock(lock_file):
        speaker.say("waits")
        time.sleep(0.2)
        speaker.interrupt()
    speaker.drain()

    assert backend.played == []


def test_drain_plays_a_sentence_queued_behind_another_session(lock_file):
    """`drain()` finishes what is queued rather than dropping it, so a sentence
    waiting for the device is heard when the other session lets go in time.

    Closing the speaker stops new sentences; it must not decide that the ones
    already waiting are unwanted.
    """
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))
    holder = _hold_the_device(lock_file, 0.5)
    speaker.say("drained")
    time.sleep(0.2)  # the player is waiting for the other session
    assert backend.played == []

    speaker.drain()
    holder.join(5)

    assert backend.played == ["drained"]
