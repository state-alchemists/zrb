"""Pin what happens to a sentence when the output device will not open: the next
one leaves the device alone, the one after tries it again, and the voice a
sentence was queued with survives the wait."""

import threading

from zrb.llm.contracts.shared.ambient_state import get_current_speech_voice
from zrb.llm.presentation.speech import Speaker, Utterance

from .render_failure_support import (
    AudioBackend,
    LocalVoice,
    _config,
    _with_local_voice,
)


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
    monkeypatch.setattr("zrb.llm.presentation.speech.player.time", clock)
    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.is_in_process_available", lambda: True
    )
    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.PcmUtterance", DeviceFailingPcm
    )
    return clock


class QuietDevicePcm(Utterance):
    """An in-process sentence whose output device cannot open, with no other
    backend to speak it."""

    def __init__(self, audio, fallback=None, on_device_error=None, **kwargs):
        super().__init__([])
        self.on_device_error = on_device_error

    def play(self, timeout):
        self.on_device_error(OSError("no default output device"))


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

    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.PcmUtterance", SignallingPcm
    )
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

    monkeypatch.setattr("zrb.llm.presentation.speech.player.PcmUtterance", RecordingPcm)
    speaker = Speaker(_config(RenderRecordingBackend(), lock_file, player="auto"))

    speaker.speak("one")

    assert told[0]() is True
    clock.advance(4)
    assert told[0]() is False


def test_a_local_voice_keeps_its_voice_while_the_device_rests(lock_file, monkeypatch):
    """Changing the output device costs a sentence its pause, not its voice:
    the local voice is rendered again rather than handed to the local engine."""
    _device_failing(monkeypatch)
    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.PcmUtterance", QuietDevicePcm
    )
    voice, local = LocalVoice(), AudioBackend(renders=False)
    _with_local_voice(monkeypatch, voice, local)
    speaker = Speaker(_config(voice, lock_file, player="auto"))

    speaker.speak("one")
    speaker.speak("two")

    assert voice.rendered == ["one", "two"]
    assert local.played == []
