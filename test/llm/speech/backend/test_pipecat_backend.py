"""Pin Pipecat backend construction, rendering, refusal, and cleanup."""

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
from zrb.llm.voice.builtin import TTS_SERVICE_SPECS  # noqa: E402
from zrb.llm.voice.registry import TTSServiceRegistry  # noqa: E402
from zrb.llm.voice.spec import TTSServiceSpec  # noqa: E402

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
    """A second sentence reuses the service and its loaded model."""
    backend = PipecatSpeechBackend("piper", SpeechConfig().resolve())
    try:
        list(backend.create_audio(SENTENCE).chunks)
        list(backend.create_audio(SENTENCE).chunks)
    finally:
        backend.close()

    assert len(factory.services) == 1
    assert factory.services[0].said == [SENTENCE, SENTENCE]


def test_a_service_that_cannot_be_built_is_reported_to_the_speaker(monkeypatch):
    """A missing package is raised for the speaker's local fallback."""

    def create_service(name: str, config: SpeechConfig) -> TTSService:
        raise RuntimeError(f"speech service {name!r} needs 'kokoro_onnx'")

    monkeypatch.setattr(
        "zrb.llm.speech.backend.pipecat.tts_manager.create_service", create_service
    )
    backend = PipecatSpeechBackend("kokoro", SpeechConfig().resolve())

    with pytest.raises(RuntimeError, match="kokoro_onnx"):
        backend.create_audio(SENTENCE)


def test_a_start_that_never_returns_is_given_up_on(monkeypatch):
    """A model load that never finishes used to park every sentence behind it,
    and the session went silent with no error. The waiting side now gives up,
    so the speaker falls back to a voice that is audible."""
    entered, release = threading.Event(), threading.Event()

    def create_service(name: str, config: SpeechConfig) -> TTSService:
        entered.set()
        release.wait(5)
        return FakeSpeechService()

    monkeypatch.setattr(
        "zrb.llm.speech.backend.pipecat.tts_manager.create_service", create_service
    )
    monkeypatch.setattr(
        "zrb.llm.speech.backend.pipecat.PIPELINE_START_TIMEOUT_SECONDS", 0.2
    )
    backend = PipecatSpeechBackend("piper", SpeechConfig().resolve())
    starter = threading.Thread(target=_drain, args=(backend,), daemon=True)
    starter.start()
    try:
        assert entered.wait(5)  # one thread is inside the start
        with pytest.raises(RuntimeError, match="still starting"):
            backend.create_audio(SENTENCE)
    finally:
        release.set()
        starter.join(5)
        backend.close()


def _drain(backend: PipecatSpeechBackend) -> None:
    """Ask *backend* for a sentence and read it, ignoring how it went."""
    try:
        list(backend.create_audio(SENTENCE).chunks)
    except Exception:
        pass


def test_the_backend_refuses_to_play_the_audio_itself(factory):
    """A renders-only service refuses direct utterance playback."""
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


def test_a_closed_backend_starts_no_second_pipeline(factory):
    backend = PipecatSpeechBackend("kokoro", SpeechConfig().resolve())
    backend.close()

    with pytest.raises(RuntimeError, match="closed"):
        backend.create_audio(SENTENCE)

    assert factory.services == []
    assert _tts_threads() == []


def test_the_backend_is_local_as_its_registered_service_is(monkeypatch):
    registry = TTSServiceRegistry(TTS_SERVICE_SPECS)
    registry.register("remote", TTSServiceSpec(name="remote", is_local=False))
    monkeypatch.setattr("zrb.llm.speech.backend.pipecat.tts_registry", registry)
    config = SpeechConfig().resolve()

    assert PipecatSpeechBackend("kokoro", config).is_local
    assert not PipecatSpeechBackend("remote", config).is_local
    assert not PipecatSpeechBackend("unknown", config).is_local


def test_closing_does_not_wait_for_a_pipeline_still_starting(monkeypatch):
    """Quitting mid-download returns at once; the late pipeline closes itself."""
    building, release = threading.Event(), threading.Event()
    built = FakeTTSServiceFactory()

    def slow_create_service(name: str, config: SpeechConfig) -> FakeSpeechService:
        building.set()
        release.wait(5)
        return built(name, config)

    monkeypatch.setattr(
        "zrb.llm.speech.backend.pipecat.tts_manager.create_service",
        slow_create_service,
    )
    backend = PipecatSpeechBackend("pocket", SpeechConfig().resolve())
    errors: list[Exception] = []

    def speak() -> None:
        try:
            backend.create_audio(SENTENCE)
        except RuntimeError as exc:
            errors.append(exc)

    speaker = threading.Thread(target=speak)
    speaker.start()
    assert building.wait(5)

    closer = threading.Thread(target=backend.close)
    closer.start()
    closer.join(1)
    is_close_blocked = closer.is_alive()
    release.set()
    speaker.join(5)

    assert not is_close_blocked
    assert [str(e) for e in errors] == ["the pocket speech service was closed"]
    assert len(built.services) == 1
    assert _tts_threads() == []
