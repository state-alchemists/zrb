"""Doubles shared by the speaker tests: a backend that records what was said,
the utterance it makes, one that plays until it is stopped, and the config
a test hands its speaker."""

import threading

from zrb.llm.contracts.shared.ambient_state import get_current_speech_voice
from zrb.llm.presentation.speech import (
    AnySpeechBackend,
    SpeechConfig,
    Utterance,
)
from zrb.llm.presentation.speech.player import is_speaking


class RecordingUtterance(Utterance):
    def __init__(self, text: str, played: list[str], done: threading.Event):
        super().__init__([])
        self.text = text
        self.played = played
        self.done = done
        self.speaking_while_played: bool | None = None
        self.cleaned = False

    def play(self, timeout):
        self.speaking_while_played = is_speaking()
        self.played.append(self.text)
        self.done.set()

    def cleanup(self):
        self.cleaned = True


class FakeBackend(AnySpeechBackend):
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.played: list[str] = []
        self.done = threading.Event()
        self.utterances: list[RecordingUtterance] = []
        self.voices: list[str] = []

    def create_utterance(self, text):
        self.voices.append(get_current_speech_voice())
        if self.fail:
            raise RuntimeError("no network")
        utterance = RecordingUtterance(text, self.played, self.done)
        self.utterances.append(utterance)
        return utterance


def _config(backend, lock_file, **fields):
    # Played by a program unless a test says otherwise: these tests are about
    # queueing, locking and stopping, not where the audio goes.
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


class HangingUtterance(Utterance):
    """Plays until stopped."""

    def __init__(self, started: threading.Event):
        super().__init__([])
        self.started = started
        self.stopped = threading.Event()
        self.is_played = False

    def play(self, timeout):
        self.is_played = True
        self.started.set()
        self.stopped.wait(5)

    def stop(self):
        self.stopped.set()


class HangingBackend(AnySpeechBackend):
    def __init__(self):
        self.started = threading.Event()
        self.utterances: list[HangingUtterance] = []

    def create_utterance(self, text):
        utterance = HangingUtterance(self.started)
        self.utterances.append(utterance)
        return utterance
