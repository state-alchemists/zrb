"""Pin what a backend that cannot render leads to: a program speaks it, and a
backend that keeps failing is dropped."""

import threading

import pytest

from zrb.llm.ambient_state import get_current_speech_voice
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
            device_is_resting=None,
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


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class DeviceFailingPcm(Utterance):
    """An in-process utterance whose output device cannot open."""

    def __init__(
        self,
        audio,
        fallback=None,
        on_device_error=None,
        device_is_resting=None,
        **kwargs,
    ):
        super().__init__([])
        self.fallback, self.on_device_error = fallback, on_device_error
        self.device_is_resting = device_is_resting

    def play(self, timeout):
        self.on_device_error(OSError("no default output device"))
        self.fallback().play(timeout)


class RenderRecordingBackend(AudioBackend):
    """Records the text and the voice each rendered sentence asked for."""

    def __init__(self):
        super().__init__()
        self.rendered: list[tuple[str, str]] = []

    def create_audio(self, text):
        self.rendered.append((text, get_current_speech_voice()))
        return super().create_audio(text)


def _device_failing(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr("zrb.llm.speech.player.time", clock)
    monkeypatch.setattr("zrb.llm.speech.player.is_in_process_available", lambda: True)
    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", DeviceFailingPcm)
    return clock


def test_a_device_that_failed_is_left_alone_for_the_sentence_after_it(
    lock_file, monkeypatch, caplog
):
    """The open that just failed is not asked again for the next sentence."""
    _device_failing(monkeypatch)
    backend = RenderRecordingBackend()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    speaker.speak("one")
    speaker.speak("two")

    assert [text for text, _ in backend.rendered] == ["one"]
    assert backend.played == ["one", "two"]
    assert caplog.text.count("Could not use the audio device") == 1


def test_a_later_sentence_tries_the_failed_output_device_again(
    lock_file, monkeypatch, caplog
):
    """A failed open means the device is changing — a speaker plugged in or
    handed over — not that in-process playback is over for the session."""
    clock = _device_failing(monkeypatch)
    backend = RenderRecordingBackend()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    speaker.speak("one")
    clock.advance(4)
    speaker.speak("two")

    assert [text for text, _ in backend.rendered] == ["one", "two"]
    assert backend.played == ["one", "two"]
    assert caplog.text.count("Could not use the audio device") == 1


def test_speech_returns_to_its_queued_voice_after_a_device_failure(
    lock_file, monkeypatch
):
    """After a speaker change, speech fell back to the configured voice and
    never came back: the sentence tried again on the device keeps the voice
    the emitter asked for, which is how a turn holds its emotion's voice."""
    clock = _device_failing(monkeypatch)
    failed = threading.Event()

    class SignallingPcm(DeviceFailingPcm):
        def play(self, timeout):
            super().play(timeout)
            failed.set()

    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", SignallingPcm)
    backend = RenderRecordingBackend()
    speaker = Speaker(_config(backend, lock_file, player="auto"))

    speaker.say("one", voice="happy.wav")
    assert failed.wait(5)
    clock.advance(4)
    speaker.say("two", voice="happy.wav")
    speaker.drain()

    assert backend.rendered == [("one", "happy.wav"), ("two", "happy.wav")]


def test_a_made_sentence_asks_whether_the_device_rests_before_it_plays(
    lock_file, monkeypatch
):
    """The device can fail while the sentence after it is already made: a
    sentence asks when it plays, not when it was rendered."""
    clock = _device_failing(monkeypatch)
    told = []

    class RecordingPcm(DeviceFailingPcm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            told.append(self.device_is_resting)

    monkeypatch.setattr("zrb.llm.speech.player.PcmUtterance", RecordingPcm)
    speaker = Speaker(_config(RenderRecordingBackend(), lock_file, player="auto"))

    speaker.speak("one")

    assert told[0]() is True
    clock.advance(4)
    assert told[0]() is False
