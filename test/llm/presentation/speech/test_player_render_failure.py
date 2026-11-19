"""Pin what a backend that cannot render leads to: a program speaks it, a
backend that keeps failing is dropped, and a local voice is asked for its own
sentence rather than replaced."""

import threading

import pytest

from zrb.llm.presentation.speech import Speaker

from .render_failure_support import (
    AudioBackend,
    LocalVoice,
    RecordingUtterance,
    _config,
    _with_local_voice,
)


class RemoteVoice(LocalVoice):
    """A paid voice whose audio zrb plays, like a registered cloud service."""

    @property
    def is_local(self) -> bool:
        return False


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
            volume=None,
            prebuffer_seconds=None,
        ):
            super().__init__(b"".join(audio.chunks).decode(), made, threading.Event())
            options.append((block_frames, read_ahead))
            fallbacks.append(fallback)

    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.is_in_process_available", lambda: available
    )
    monkeypatch.setattr("zrb.llm.presentation.speech.player.PcmUtterance", FakePcm)
    return made


def _built_by_zrb(monkeypatch, backend):
    """Hand the speaker a name, so what it speaks with is its own to close."""
    monkeypatch.setattr(
        "zrb.llm.presentation.speech.player.get_speech_backend",
        lambda name, config: backend,
    )
    return backend


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
    lock_file, monkeypatch, caplog
):
    _in_process(monkeypatch)

    class DeadService(AudioBackend):
        closed = 0

        def create_audio(self, text):
            raise RuntimeError("service no longer usable")

        def close(self):
            self.closed += 1

    backend = _built_by_zrb(monkeypatch, DeadService())
    speaker = Speaker(_config("dead", lock_file, player="auto"))

    for text in ("one", "two", "three"):
        speaker.speak(text)
    assert backend.closed == 0
    assert "Replacing the speech backend" not in caplog.text
    speaker.speak("four")

    assert backend.closed == 1
    # Why the backend was replaced is not left to be inferred from silence.
    assert "Replacing the speech backend after 3 sentence(s)" in caplog.text


def test_the_sentence_that_lost_its_backend_still_falls_back_with_it(
    lock_file, monkeypatch
):
    """The drop waits for the next sentence. Closing it here would close it
    under the sentence that is still being made from it, which is how a
    service kept being reported as closed for the rest of a session."""
    _in_process(monkeypatch)
    seen: "list[int]" = []

    class DeadService(AudioBackend):
        def __init__(self):
            super().__init__(renders=False)
            self.closed = 0

        def create_audio(self, text):
            raise RuntimeError("the pocket service was closed")

        def create_utterance(self, text):
            seen.append(self.closed)
            return super().create_utterance(text)

        def close(self):
            self.closed += 1

    speaker = Speaker(_config(DeadService(), lock_file, player="auto"))

    for text in ("one", "two", "three"):
        speaker.speak(text)

    assert seen == [0, 0, 0]


def test_restarting_backends_closes_the_ones_zrb_built(lock_file, monkeypatch):
    _in_process(monkeypatch)
    backend = _built_by_zrb(monkeypatch, AudioBackend())
    backend.close = lambda: backend.played.append("closed")
    speaker = Speaker(_config("configured", lock_file, player="auto"))
    speaker.speak("hello")

    speaker.restart_backends()

    assert backend.played == ["closed"]


def test_a_local_voice_is_not_read_by_the_local_engine(lock_file, monkeypatch, caplog):
    """`say` is another voice, not a worse take on this one: a local voice zrb
    can play reports the failure instead of being replaced."""
    _in_process(monkeypatch)
    local = AudioBackend(renders=False)

    class BrokenVoice(LocalVoice):
        def create_audio(self, text):
            raise RuntimeError("the model is not loaded")

    _with_local_voice(monkeypatch, BrokenVoice(), local)
    speaker = Speaker(_config("pocket", lock_file, player="auto"))

    with pytest.raises(RuntimeError):
        speaker.speak("hello")

    assert local.played == []
    assert "this sentence goes unsaid" in caplog.text


def test_a_local_voice_that_made_no_audio_is_asked_for_the_sentence_again(
    lock_file, monkeypatch, caplog
):
    """A context that came back empty is the engine's slip, not the sentence's:
    Pipecat reports one as a context that completed with no audio, and a local
    voice that believes it the first time leaves the sentence unsaid."""
    made = _in_process(monkeypatch)
    asked = []

    class SilentOnce(LocalVoice):
        def __init__(self):
            super().__init__()
            self.is_first = True

        def create_audio(self, text):
            asked.append(text)
            if self.is_first:
                self.is_first = False
                raise RuntimeError("TTS context completed with no audio")
            return super().create_audio(text)

    _with_local_voice(monkeypatch, SilentOnce(), AudioBackend(renders=False))
    speaker = Speaker(_config("pocket", lock_file, player="auto"))

    speaker.speak("hello")

    assert asked == ["hello", "hello"]
    assert made == ["hello"]
    assert "goes unsaid" not in caplog.text


def test_a_remote_voice_is_asked_once_for_a_sentence(lock_file, monkeypatch):
    """A render nobody hears is still billed, so only a local voice, which has
    no other way to speak the sentence, is asked again."""
    _in_process(monkeypatch)
    asked = []

    class BrokenRemote(RemoteVoice):
        def create_audio(self, text):
            asked.append(text)
            raise RuntimeError("the service is down")

    _with_local_voice(monkeypatch, BrokenRemote(), AudioBackend(renders=False))
    speaker = Speaker(_config("remote", lock_file, player="auto"))

    speaker.speak("hello")

    assert asked == ["hello"]


def test_a_sentence_that_stayed_silent_is_named_in_the_log(
    lock_file, monkeypatch, caplog
):
    """The log says which sentence was lost, so it can be tried again by hand
    rather than guessed at from a gap in what was heard."""
    _in_process(monkeypatch)

    class AlwaysSilent(LocalVoice):
        def create_audio(self, text):
            raise RuntimeError("TTS context completed with no audio")

    _with_local_voice(monkeypatch, AlwaysSilent(), AudioBackend(renders=False))
    speaker = Speaker(_config("pocket", lock_file, player="auto"))

    with pytest.raises(RuntimeError):
        speaker.speak("the fix is on its way")

    assert "'the fix is on its way'" in caplog.text


def test_a_remote_voice_that_fails_is_read_by_the_local_engine(lock_file, monkeypatch):
    """A paid voice that fails is read by the local engine, as documented."""
    _in_process(monkeypatch)
    local = AudioBackend(renders=False)

    class BrokenRemote(RemoteVoice):
        def create_audio(self, text):
            raise RuntimeError("the service is down")

    _with_local_voice(monkeypatch, BrokenRemote(), local)
    speaker = Speaker(_config("remote", lock_file, player="auto"))

    speaker.speak("hello")

    assert local.played == ["hello"]
