"""Doubles shared by the render-failure tests: a backend that records what was
said, one that optionally renders audio, and a local voice zrb renders and
plays itself."""

import threading

from zrb.llm.presentation.speech import (
    AnySpeechBackend,
    SpeechConfig,
    Utterance,
)
from zrb.llm.presentation.speech.backend.audio import SpeechAudio


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


def _config(backend, lock_file, **fields):
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


class AudioBackend(FakeBackend):
    """A backend that optionally renders audio."""

    def __init__(self, renders=True):
        super().__init__()
        self.renders = renders

    def create_audio(self, text):
        if not self.renders:
            return None
        return SpeechAudio(16000, [text.encode()])


class LocalVoice(AudioBackend):
    """A local voice zrb renders and plays itself, recording what it made."""

    def __init__(self):
        super().__init__()
        self.rendered: list[str] = []

    @property
    def name(self) -> str:
        return "Pipecat (test)"

    @property
    def needs_zrb_playback(self) -> bool:
        return True

    @property
    def is_local(self) -> bool:
        return True

    def create_utterance(self, text):
        raise RuntimeError("plays in process only")

    def create_audio(self, text):
        self.rendered.append(text)
        return super().create_audio(text)


def _with_local_voice(monkeypatch, voice, local):
    """The configured *voice* for anything but 'auto', the local engine for it."""
    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.get_speech_backend",
        lambda name, config: local if name == "auto" else voice,
    )
