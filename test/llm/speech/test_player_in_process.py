"""`Speaker`: playing in process when it can, and pausing."""

import threading

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.backend.audio import SpeechAudio


class RecordingUtterance(Utterance):
    def __init__(self, text, played, done):
        super().__init__([])
        self.text, self.played, self.done = text, played, done

    def play(self, timeout):
        self.played.append(self.text)
        self.done.set()


class FakeBackend(AnySpeechBackend):
    def __init__(self):
        self.played: list[str] = []

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played, threading.Event())


class HangingUtterance(Utterance):
    """Plays until stopped."""

    def __init__(self, started):
        super().__init__([])
        self.started = started
        self.stopped = threading.Event()

    def play(self, timeout):
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


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file, **fields):
    fields.setdefault("player", "command")
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


class AudioBackend(FakeBackend):
    """Renders audio when *renders*, else only plays."""

    def __init__(self, renders=True):
        super().__init__()
        self.renders = renders

    def create_audio(self, text):
        if not self.renders:
            return None
        return SpeechAudio(16000, [text.encode()])


def _in_process(monkeypatch, available=True, options=None):
    made = []
    options = [] if options is None else options

    class FakePcm(RecordingUtterance):
        def __init__(self, audio, block_frames=None, read_ahead=None):
            super().__init__(b"".join(audio.chunks).decode(), made, threading.Event())
            options.append((block_frames, read_ahead))

    monkeypatch.setattr(
        "zrb.llm.speech.player.is_in_process_available", lambda: available
    )
    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", FakePcm)
    return made


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


def test_pause_holds_a_pausable_utterance_and_resume_carries_on(lock_file):
    backend = HangingBackend()
    backend.create_utterance = (
        lambda text: backend.utterances.append(PausableUtterance(backend.started))
        or backend.utterances[-1]
    )
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()  # nothing playing: nothing to do
    speaker.say("long")
    assert backend.started.wait(1)

    speaker.pause()
    speaker.resume()

    assert backend.utterances[0].events == ["pause", "resume"]
    speaker.close()


def test_pause_interrupts_speech_that_cannot_pause(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.resume()  # nothing playing: nothing to do
    speaker.say("long")
    assert backend.started.wait(1)

    speaker.pause()

    assert backend.utterances[0].stopped.is_set()
    speaker.close()


def _slow_backend(created, release):
    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            created.set()
            release.wait(5)
            return super().create_utterance(text)

    return SlowBackend()


@pytest.mark.parametrize("switch_off", [True, False])
def test_speech_being_made_when_cleared_is_never_played(lock_file, switch_off):
    """/speech off (or clearing the queue) while a sentence is still being
    synthesized drops that sentence once it is made."""
    created, release = threading.Event(), threading.Event()
    backend = _slow_backend(created, release)
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("in the making")
    assert created.wait(1)

    if switch_off:
        speaker.is_enabled = False
    speaker.clear()
    release.set()
    speaker.drain()

    assert backend.played == []


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
