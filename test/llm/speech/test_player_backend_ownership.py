"""Pin who closes a speech backend: the speaker its own, the caller its own."""

import threading

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.backend.audio import SpeechAudio


class RecordingUtterance(Utterance):
    def __init__(self, text, played, done):
        super().__init__([])
        self.text, self.played, self.done = text, played, done

    def play(self, timeout):
        self.report_started()
        self.played.append(self.text)
        self.done.set()


class ClosingBackend(AnySpeechBackend):
    """A backend that says when it was closed."""

    def __init__(self):
        self.played: list[str] = []
        self.closed = 0

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played, threading.Event())

    def create_audio(self, text):
        return SpeechAudio(16000, [text.encode()])

    def close(self):
        self.closed += 1


class LocalVoice(ClosingBackend):
    """A local voice zrb renders and plays itself, dead once closed."""

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
        if self.closed:
            raise RuntimeError("the test speech service was closed")
        return super().create_audio(text)


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file, **fields):
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


def _in_process(monkeypatch, made=None):
    made = [] if made is None else made

    class FakePcm(RecordingUtterance):
        def __init__(self, audio, **kwargs):
            super().__init__(b"".join(audio.chunks).decode(), made, threading.Event())

    monkeypatch.setattr("zrb.llm.speech.player.is_in_process_available", lambda: True)
    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", FakePcm)
    return made


def _built_by_zrb(monkeypatch, backend):
    """Hand the speaker a name, so what it speaks with is its own to close."""
    monkeypatch.setattr(
        "zrb.llm.speech.player.get_speech_backend", lambda name, config: backend
    )
    return backend


def test_a_backend_the_caller_supplied_is_not_closed_when_the_speaker_ends(lock_file):
    """The caller made it and outlives the speaker: a chat makes a speaker a
    session, so closing it left the next session with a dead one."""
    voice = ClosingBackend()
    speaker = Speaker(_config(voice, lock_file))

    speaker.speak("one")
    speaker.close()

    assert voice.played == ["one"]
    assert voice.closed == 0


def test_a_backend_zrb_built_is_closed_when_the_speaker_ends(lock_file, monkeypatch):
    voice = _built_by_zrb(monkeypatch, ClosingBackend())
    speaker = Speaker(_config("configured", lock_file))

    speaker.speak("one")
    speaker.close()

    assert voice.played == ["one"]
    assert voice.closed == 1


def test_a_backend_the_caller_supplied_is_not_closed_by_a_restart(
    lock_file, monkeypatch
):
    _in_process(monkeypatch)
    voice = LocalVoice()
    speaker = Speaker(_config(voice, lock_file, player="auto"))
    speaker.speak("one")

    speaker.restart_backends()

    assert voice.closed == 0


def test_a_supplied_voice_still_speaks_in_the_next_session(lock_file, monkeypatch):
    """One chat, several sessions. The voice it was given is the same object
    every time, so a session that closed it made every sentence after it fall
    back to another voice."""
    made = _in_process(monkeypatch)
    voice = LocalVoice()
    config = _config(voice, lock_file, player="auto")

    first = Speaker(config)
    first.speak("one")
    first.close()
    second = Speaker(config)
    second.speak("two")

    assert made == ["one", "two"]
    assert voice.closed == 0
