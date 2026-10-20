"""Pin which backend speaks a sentence in process, and what plays it instead."""

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


class RendersOnlyBackend(AudioBackend):
    """A renders-only backend with no player program."""

    @property
    def name(self):
        return "Pipecat (test)"

    @property
    def needs_zrb_playback(self):
        return True

    def create_utterance(self, text):
        raise RuntimeError("renders audio for zrb to play in process")


def _with_local_voice(monkeypatch, service, local):
    monkeypatch.setattr(
        "zrb.llm.speech.player.get_speech_backend",
        lambda name, config: local if name == "auto" else service,
    )


def test_audio_a_backend_renders_is_played_in_process(lock_file, monkeypatch):
    made = _in_process(monkeypatch)
    backend = AudioBackend()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    speaker.speak("hello")

    assert made == ["hello"]
    assert backend.played == []


def test_in_process_playback_takes_its_block_and_read_ahead_from_config(
    lock_file, monkeypatch
):
    options = []
    _in_process(monkeypatch, options=options)
    config = _config(
        AudioBackend(),
        lock_file,
        player="auto",
        player_block_frames=256,
        player_read_ahead=4,
    )

    Speaker(config).speak("hello")

    assert options == [(256, 4)]


@pytest.mark.parametrize(
    "player, available, renders",
    [("command", True, True), ("auto", False, True), ("auto", True, False)],
)
def test_speech_is_played_by_a_program_otherwise(
    lock_file, monkeypatch, player, available, renders
):
    made = _in_process(monkeypatch, available)
    backend = AudioBackend(renders)
    speaker = Speaker(_config(backend, lock_file, player=player))

    speaker.speak("hello")

    assert made == []
    assert backend.played == ["hello"]


def test_in_process_speech_falls_back_to_the_backends_own_utterance(
    lock_file, monkeypatch
):
    fallbacks = []
    _in_process(monkeypatch, fallbacks=fallbacks)
    backend = AudioBackend()
    Speaker(_config(backend, lock_file, player="auto")).speak("hello")

    fallbacks[0]().play(None)
    assert backend.played == ["hello"]


def test_a_service_is_not_asked_to_play_when_zrb_cannot_play_it(
    lock_file, monkeypatch, caplog
):
    """A configured player program bypasses the renders-only service."""
    _in_process(monkeypatch)
    service, local = RendersOnlyBackend(), AudioBackend()
    _with_local_voice(monkeypatch, service, local)

    Speaker(_config(service, lock_file, player="command")).speak("hello")

    assert local.played == ["hello"]
    assert "failed" not in caplog.text


def test_a_device_that_fails_hands_a_service_s_sentence_to_the_local_voice(
    lock_file, monkeypatch
):
    """Device failure sends rendered speech to the local voice."""
    fallbacks = []
    _in_process(monkeypatch, fallbacks=fallbacks)
    service, local = RendersOnlyBackend(), AudioBackend()
    _with_local_voice(monkeypatch, service, local)
    Speaker(_config(service, lock_file, player="auto")).speak("hello")

    fallbacks[0]().play(None)

    assert local.played == ["hello"]
    assert service.played == []


def test_an_unknown_player_is_logged_and_read_as_auto(lock_file, monkeypatch, caplog):
    made = _in_process(monkeypatch)
    backend = AudioBackend()

    Speaker(_config(backend, lock_file, player="commands")).speak("hello")

    assert "Unknown speech player 'commands'" in caplog.text
    assert made == ["hello"]
