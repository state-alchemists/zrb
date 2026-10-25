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


def _in_process(
    monkeypatch,
    available=True,
    options=None,
    fallbacks=None,
    volumes=None,
    cushions=None,
):
    made = []
    options = [] if options is None else options
    fallbacks = [] if fallbacks is None else fallbacks
    seen_volumes: list[int | None] = [] if volumes is None else volumes
    seen_cushions: list[float | None] = [] if cushions is None else cushions

    class FakePcm(RecordingUtterance):
        def __init__(
            self,
            audio,
            block_frames=None,
            read_ahead=None,
            fallback=None,
            on_device_error=None,
            device_is_resting=None,
            volume=None,
            prebuffer_seconds=None,
        ):
            super().__init__(b"".join(audio.chunks).decode(), made, threading.Event())
            options.append((block_frames, read_ahead))
            fallbacks.append(fallback)
            seen_volumes.append(volume)
            seen_cushions.append(prebuffer_seconds)

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
    cushions = []
    _in_process(monkeypatch, options=options, cushions=cushions)
    config = _config(
        AudioBackend(),
        lock_file,
        player="auto",
        player_block_frames=256,
        player_read_ahead=4,
        player_prebuffer_seconds=0.6,
    )

    Speaker(config).speak("hello")

    assert options == [(256, 4)]
    assert cushions == [0.6]


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


def test_a_sentence_is_played_at_the_speakers_volume(lock_file, monkeypatch):
    volumes = []
    _in_process(monkeypatch, volumes=volumes)
    speaker = Speaker(_config(AudioBackend(), lock_file, player="auto", volume=60))

    speaker.speak("hello")

    assert volumes == [60]


def test_a_volume_change_steers_the_next_sentence(lock_file, monkeypatch):
    volumes = []
    _in_process(monkeypatch, volumes=volumes)
    speaker = Speaker(_config(AudioBackend(), lock_file, player="auto"))

    speaker.set_volume(150)
    speaker.speak("hello")

    assert volumes == [150]


@pytest.mark.parametrize("asked, held", [(500, 200), (-20, 0), (60, 60)])
def test_the_volume_is_held_inside_what_zrb_speaks_at(lock_file, asked, held):
    speaker = Speaker(_config(AudioBackend(), lock_file))

    speaker.set_volume(asked)

    assert speaker.volume == held


def test_audio_zrb_plays_itself_is_where_a_volume_applies(lock_file, monkeypatch):
    _in_process(monkeypatch)
    speaker = Speaker(_config(AudioBackend(), lock_file, player="auto"))

    assert speaker.is_playing_in_process is True


def test_a_player_program_is_not_where_a_volume_applies(lock_file):
    speaker = Speaker(_config(AudioBackend(), lock_file, player="command"))

    assert speaker.is_playing_in_process is False


def test_a_cloud_voice_that_hands_its_audio_to_a_player_keeps_its_own_volume(
    lock_file, monkeypatch
):
    """A backend that renders nothing leaves the playing to a program, so zrb
    never sees the samples a volume would scale."""
    _in_process(monkeypatch)
    speaker = Speaker(_config(AudioBackend(renders=False), lock_file, player="auto"))

    speaker.speak("hello")

    assert speaker.is_playing_in_process is False


def test_a_local_engine_that_renders_for_zrb_is_where_a_volume_applies(
    lock_file, monkeypatch
):
    """`say` and `espeak-ng` say no to `needs_zrb_playback` and still render a
    WAV for zrb to play, so what matters is the sentence that was made."""
    _in_process(monkeypatch)
    speaker = Speaker(_config(AudioBackend(), lock_file, player="auto"))

    speaker.speak("hello")

    assert speaker.is_playing_in_process is True


def test_a_sentence_a_program_takes_over_is_not_where_a_volume_applies(
    lock_file, monkeypatch
):
    """The device failed and a program spoke instead: what was heard did not
    pass through the volume, so the next answer must not promise it did."""
    fallbacks = []
    _in_process(monkeypatch, fallbacks=fallbacks)
    speaker = Speaker(_config(AudioBackend(), lock_file, player="auto"))

    speaker.speak("hello")
    fallbacks[0]().play(None)

    assert speaker.is_playing_in_process is False
