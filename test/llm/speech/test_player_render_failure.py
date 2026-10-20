"""Pin what a backend that cannot render leads to: a program speaks it, and a
backend that keeps failing is dropped."""

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


class FakeBackend(AnySpeechBackend):
    def __init__(self):
        self.played: list[str] = []

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played, threading.Event())


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


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


def _in_process(monkeypatch, available=True, options=None, fallbacks=None):
    made = []
    options = [] if options is None else options
    fallbacks = [] if fallbacks is None else fallbacks

    class FakePcm(RecordingUtterance):
        def __init__(
            self,
            audio,
            block_frames=None,
            read_ahead=None,
            fallback=None,
            on_device_error=None,
        ):
            super().__init__(b"".join(audio.chunks).decode(), made, threading.Event())
            options.append((block_frames, read_ahead))
            fallbacks.append(fallback)

    monkeypatch.setattr(
        "zrb.llm.speech.player.is_in_process_available", lambda: available
    )
    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", FakePcm)
    return made


def test_audio_that_fails_to_render_is_spoken_by_a_player_program(
    lock_file, monkeypatch, caplog
):
    made = _in_process(monkeypatch)

    class BrokenRender(AudioBackend):
        def create_audio(self, text):
            raise RuntimeError("say could not write the WAV")

    backend = BrokenRender()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    speaker.speak("hello")

    assert made == []
    assert backend.played == ["hello"]
    assert "could not write the WAV" in caplog.text


def test_a_backend_that_fails_to_render_three_times_in_a_row_is_dropped(
    lock_file, monkeypatch
):
    _in_process(monkeypatch)

    class DeadService(AudioBackend):
        closed = 0

        def create_audio(self, text):
            raise RuntimeError("service no longer usable")

        def close(self):
            self.closed += 1

    backend = DeadService()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    for text in ("one", "two"):
        speaker.speak(text)
    assert backend.closed == 0
    speaker.speak("three")

    assert backend.closed == 1


def test_restarting_backends_closes_the_cached_ones(lock_file, monkeypatch):
    _in_process(monkeypatch)
    backend = AudioBackend()
    backend.close = lambda: backend.played.append("closed")
    speaker = Speaker(_config(backend, lock_file, player="auto"))
    speaker.speak("hello")

    speaker.restart_backends()

    assert backend.played == ["closed"]


def test_an_output_device_that_cannot_open_is_not_tried_again(
    lock_file, monkeypatch, caplog
):
    """An unavailable output device is not retried for the same sentence."""
    rendered: list[str] = []

    class FailingPcm(Utterance):
        def __init__(self, audio, fallback=None, on_device_error=None, **kwargs):
            super().__init__([])
            self.fallback, self.on_device_error = fallback, on_device_error

        def play(self, timeout):
            self.on_device_error(OSError("no default output device"))
            self.fallback().play(timeout)

    class CountingBackend(AudioBackend):
        def create_audio(self, text):
            rendered.append(text)
            return super().create_audio(text)

    monkeypatch.setattr("zrb.llm.speech.player.is_in_process_available", lambda: True)
    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", FailingPcm)
    backend = CountingBackend()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    speaker.speak("one")
    speaker.speak("two")

    assert rendered == ["one"]
    assert backend.played == ["one", "two"]
    assert caplog.text.count("Could not use the audio device") == 1
