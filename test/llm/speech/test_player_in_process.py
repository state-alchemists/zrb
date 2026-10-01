"""`Speaker`: playing in process when it can, and pausing."""

import threading
import time

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.spoken_log import SpokenLog
from zrb.util.file_lock import hold_file_lock


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
    speaker.say("long")
    assert backend.started.wait(1)

    speaker.pause()
    speaker.resume()

    assert backend.utterances[0].events == ["pause", "resume"]
    speaker.close()


def test_pause_stops_only_the_sentence_that_cannot_pause(lock_file):
    """A player program cannot hold, so its sentence stops; what follows is
    held, not dropped, so a false alarm resumes with the next sentence."""
    started, release = threading.Event(), threading.Event()
    played: list[str] = []

    class Backend(AnySpeechBackend):
        def create_utterance(self, text):
            if text == "first":
                return HangingUtterance(started)
            return RecordingUtterance(text, played, release)

    speaker = Speaker(_config(Backend(), lock_file))
    speaker.resume()  # nothing playing: nothing to do
    speaker.say("first")
    speaker.say("second")
    assert started.wait(1)

    speaker.pause()
    assert not release.wait(0.3)  # held while paused

    speaker.resume()
    assert release.wait(1)
    assert played == ["second"]
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


class SignallingBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.done = threading.Event()

    def create_utterance(self, text):
        return RecordingUtterance(text, self.played, self.done)


def test_speech_made_while_paused_waits_for_resume(lock_file):
    backend = SignallingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()  # a barge-in before anything is playing

    speaker.say("queued")
    assert not backend.done.wait(0.3)

    speaker.resume()
    assert backend.done.wait(1)
    assert backend.played == ["queued"]
    speaker.close()


def test_interrupting_a_pause_drops_what_waited_and_unpauses(lock_file):
    backend = SignallingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()
    speaker.say("dropped")
    assert not backend.done.wait(0.3)

    speaker.interrupt()
    speaker.say("next")

    assert backend.done.wait(1)
    assert backend.played == ["next"]
    speaker.close()


def test_closing_a_paused_speaker_does_not_hang(lock_file):
    backend = SignallingBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.pause()
    speaker.say("never")
    speaker.close()
    assert not backend.done.wait(0.3)
    assert backend.played == []


def test_in_process_speech_falls_back_to_the_backends_own_utterance(
    lock_file, monkeypatch
):
    fallbacks = []
    _in_process(monkeypatch, fallbacks=fallbacks)
    backend = AudioBackend()
    Speaker(_config(backend, lock_file, player="auto")).speak("hello")

    # What plays if the device cannot open: the backend's own way.
    fallbacks[0]().play(None)
    assert backend.played == ["hello"]


def test_drain_does_not_wait_for_speech_a_pause_holds(lock_file):
    backend = SignallingBackend()
    config = SpeechConfig(
        backend=backend,
        lock_file=lock_file,
        lock_timeout=0.05,
        player="command",
        drain_timeout=5,
    ).resolve()
    speaker = Speaker(config)
    speaker.pause()
    speaker.say("held")

    started = time.monotonic()
    speaker.drain()

    assert time.monotonic() - started < 2
    assert backend.played == []


def test_an_output_device_that_cannot_open_is_not_tried_again(
    lock_file, monkeypatch, caplog
):
    """Each try would ask a cloud backend for the sentence twice: once for
    zrb to play, once for the player program."""
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
    assert caplog.text.count("Could not open the audio device") == 1


def test_an_unknown_player_is_logged_and_read_as_auto(lock_file, monkeypatch, caplog):
    made = _in_process(monkeypatch)
    backend = AudioBackend()

    Speaker(_config(backend, lock_file, player="commands")).speak("hello")

    assert "Unknown speech player 'commands'" in caplog.text
    assert made == ["hello"]


def test_what_zrb_plays_is_logged_as_said_while_it_plays(lock_file, monkeypatch):
    log = SpokenLog()
    monkeypatch.setattr("zrb.llm.speech.player.spoken_log", log)
    backend = FakeBackend()
    before = time.monotonic()

    Speaker(_config(backend, lock_file)).speak("Sleep well.")

    assert log.get_text_said(before, time.monotonic()) == "Sleep well."


def test_speech_dropped_waiting_for_the_audio_device_is_not_logged_as_said(
    lock_file, monkeypatch
):
    """Another session holding the device past the lock timeout drops the
    sentence unheard; logging it anyway would have dictation drop the user
    saying the same words as zrb's echo."""
    log = SpokenLog()
    monkeypatch.setattr("zrb.llm.speech.player.spoken_log", log)
    backend = FakeBackend()
    before = time.monotonic()

    with hold_file_lock(lock_file):
        Speaker(_config(backend, lock_file)).speak("Sleep well.")

    assert backend.played == []
    assert log.get_text_said(before, time.monotonic()) == ""


def test_a_paused_sentence_is_not_logged_as_said_while_it_is_held(
    lock_file, monkeypatch
):
    """zrb is silent while paused, so what the user says then, even zrb's
    own words ("run the tests"), is theirs; the log resumes with zrb."""
    log = SpokenLog()
    monkeypatch.setattr("zrb.llm.speech.player.spoken_log", log)
    backend = HangingBackend()
    backend.create_utterance = (
        lambda text: backend.utterances.append(PausableUtterance(backend.started))
        or backend.utterances[-1]
    )
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("run the tests")
    assert backend.started.wait(1)

    speaker.pause()
    held_from = time.monotonic()
    time.sleep(0.02)
    held_until = time.monotonic()
    said_while_held = log.get_text_said(held_from, held_until)
    speaker.resume()
    resumed = time.monotonic()

    assert said_while_held == ""
    assert log.get_text_said(resumed, resumed) == "run the tests"
    speaker.close()
