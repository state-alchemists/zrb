"""`PipecatSpeechBackend`: a service renders the audio, zrb plays it.

No model is installed here and none is needed: the service is faked at the seam
the backend uses to build one, which is also the seam a project's own service
comes through. What is under test is what zrb does with it — build it once, hand
it a sentence, play its audio, and let it go — and what it refuses to do, which is
let a service play the audio itself.
"""

from __future__ import annotations

import threading

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from pipecat.frames.frames import TTSAudioRawFrame  # noqa: E402
from pipecat.services.settings import TTSSettings  # noqa: E402
from pipecat.services.tts_service import TTSService  # noqa: E402

from zrb.config.config import CFG  # noqa: E402
from zrb.llm.speech import SpeechConfig  # noqa: E402
from zrb.llm.speech.backend.pipecat import PipecatSpeechBackend  # noqa: E402

RATE = 24000
CHUNK = b"\x11\x22" * 400
SENTENCE = "hello there"


class FakeSpeechService(TTSService):
    """A service that says what it is given, in one chunk, at its own rate."""

    def __init__(self) -> None:
        super().__init__(
            sample_rate=RATE,
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(model=None, voice=None, language=None),
        )
        self.said: list[str] = []

    async def run_tts(self, text: str, context_id: str):
        self.said.append(text)
        yield TTSAudioRawFrame(
            audio=CHUNK, sample_rate=RATE, num_channels=1, context_id=context_id
        )


class FakeTTSServiceFactory:
    """What `tts_manager.create_service` is replaced with, and what it was asked."""

    def __init__(self) -> None:
        self.services: list[FakeSpeechService] = []
        self.asked: list[tuple[str, str]] = []

    def __call__(self, name: str, config: SpeechConfig) -> FakeSpeechService:
        self.asked.append((name, config.voice or ""))
        service = FakeSpeechService()
        self.services.append(service)
        return service


@pytest.fixture
def factory(monkeypatch) -> FakeTTSServiceFactory:
    """Build a fake service where the manager would build one."""
    factory = FakeTTSServiceFactory()
    monkeypatch.setattr(
        "zrb.llm.speech.backend.pipecat.tts_manager.create_service", factory
    )
    return factory


def _tts_threads() -> list[threading.Thread]:
    prefix = f"{CFG.ROOT_GROUP_NAME}-speech-tts"
    return [thread for thread in threading.enumerate() if thread.name == prefix]


def test_a_sentence_is_rendered_by_the_service_the_config_names(factory):
    """The service is asked for by name, with the config that names its voice."""
    backend = PipecatSpeechBackend("kokoro", SpeechConfig(voice="af_heart").resolve())
    try:
        audio = backend.create_audio(SENTENCE)
        chunks = list(audio.chunks)
        sample_rate = audio.sample_rate
    finally:
        backend.close()

    assert factory.asked == [("kokoro", "af_heart")]
    assert factory.services[0].said == [SENTENCE]
    assert chunks == [CHUNK]
    assert sample_rate == RATE


def test_the_service_is_built_once_for_the_backend(factory):
    """A second sentence reuses the service, and the model it loaded.

    The speaker prepares the next sentence while the current one plays, so this
    is asked for twice in a session; a service built twice would load the model
    twice.
    """
    backend = PipecatSpeechBackend("piper", SpeechConfig().resolve())
    try:
        list(backend.create_audio(SENTENCE).chunks)
        list(backend.create_audio(SENTENCE).chunks)
    finally:
        backend.close()

    assert len(factory.services) == 1
    assert factory.services[0].said == [SENTENCE, SENTENCE]


def test_a_service_that_cannot_be_built_is_reported_to_the_speaker(monkeypatch):
    """A missing package is raised where the speaker can fall back on a local voice.

    The alternative is a session that says nothing at all, which is what a
    swallowed failure looks like from the other side of the microphone.
    """

    def create_service(name: str, config: SpeechConfig) -> TTSService:
        raise RuntimeError(f"speech service {name!r} needs 'kokoro_onnx'")

    monkeypatch.setattr(
        "zrb.llm.speech.backend.pipecat.tts_manager.create_service", create_service
    )
    backend = PipecatSpeechBackend("kokoro", SpeechConfig().resolve())

    with pytest.raises(RuntimeError, match="kokoro_onnx"):
        backend.create_audio(SENTENCE)


def test_the_backend_refuses_to_play_the_audio_itself(factory):
    """A service that renders audio has no player program, and says so.

    This is what tells the speaker to say the sentence through the local voice
    instead of dropping it.
    """
    backend = PipecatSpeechBackend("kokoro", SpeechConfig().resolve())

    with pytest.raises(RuntimeError, match="kokoro.*renders audio"):
        backend.create_utterance(SENTENCE)

    assert factory.services == []


def test_closing_the_backend_stops_the_pipeline_and_is_safe_to_repeat(factory):
    """Closing lets the model and the pipeline thread go, and closes nothing twice."""
    assert _tts_threads() == []
    backend = PipecatSpeechBackend("kokoro", SpeechConfig().resolve())
    list(backend.create_audio(SENTENCE).chunks)
    assert _tts_threads() != []

    backend.close()
    backend.close()

    assert _tts_threads() == []


def test_closing_a_backend_that_never_spoke_closes_nothing(factory):
    """A session that named a service it never used has nothing to release."""
    backend = PipecatSpeechBackend("kokoro", SpeechConfig().resolve())

    backend.close()

    assert factory.services == []
    assert _tts_threads() == []
