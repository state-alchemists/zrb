"""Dictation transcribed by a Pipecat speech-to-text service.

No model is installed here and none is needed. The pipeline is stubbed, because
what is under test is the wiring around it: that the service is built once and
the same pipeline answers every utterance, that a model which will not load is
reported to whoever asked for it, and that a session which ends lets the service
go. What the pipeline does with an utterance is
`test/llm/dictation/test_pipecat_stt.py`.
"""

from __future__ import annotations

import asyncio

import pytest

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.pipecat import PipecatDictationBackend
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.feature import DictationSession

MODULE = "zrb.llm.dictation.backend.pipecat"

# A sample rate to start a stubbed pipeline at; the real one is Pipecat's own.
SAMPLE_RATE = 16000


class FakePipeline:
    """The pipeline a service would be transcribing through."""

    def __init__(self) -> None:
        self.segments: list[bytes] = []
        self.closes = 0

    async def transcribe(self, audio: bytes) -> str:
        self.segments.append(audio)
        return "hello there"

    async def close(self) -> None:
        self.closes += 1


class FakeService:
    """A service, as far as this file is concerned: something to build."""


def _config(**kwargs) -> DictationConfig:
    return DictationConfig(**kwargs).resolve()


def _stub(monkeypatch, built: list[str], pipeline: FakePipeline) -> None:
    """Stand in for the service factory and for the pipeline it is started in.

    The factory is what loads a model, and the pipeline is what starts a Pipecat
    worker; neither belongs in a test of the wiring around them.
    """

    def create_service(name: str, config: DictationConfig) -> FakeService:
        built.append(name)
        return FakeService()

    async def start(service: FakeService, sample_rate: int = SAMPLE_RATE):
        return pipeline

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    monkeypatch.setattr(f"{MODULE}.STTPipeline.start", start)


@pytest.mark.asyncio
async def test_the_service_is_built_once_and_answers_every_utterance(monkeypatch):
    """One model, one pipeline, however many recordings a session makes.

    `prepare` runs before every push-to-talk recording, not only the first, so
    building there would load the model again for each one — which for Whisper
    is a gigabyte read per recording.
    """
    pipeline = FakePipeline()
    built: list[str] = []
    _stub(monkeypatch, built, pipeline)
    backend = PipecatDictationBackend("moonshine", _config())

    reports: list[str] = []
    await backend.prepare(reports.append)
    await backend.prepare(reports.append)
    first = await backend.transcribe(b"one")
    second = await backend.transcribe(b"two")

    assert built == ["moonshine"]
    assert reports == ["Loading the moonshine speech service…"]
    assert (first, second) == ("hello there", "hello there")
    assert pipeline.segments == [b"one", b"two"]


@pytest.mark.asyncio
async def test_the_backend_is_named_after_the_service_it_was_built_from():
    """A message says which service answered, not only that Pipecat did."""
    backend = PipecatDictationBackend("whisper", _config())
    assert backend.name == "Pipecat (whisper)"


@pytest.mark.asyncio
async def test_transcribing_without_preparing_still_transcribes(monkeypatch):
    """A backend used without a `prepare` is not left without a pipeline.

    Every session prepares before it records, and saying it here as well means a
    caller that did not gets a transcript rather than a failure about a pipeline
    it never asked about.
    """
    pipeline = FakePipeline()
    _stub(monkeypatch, [], pipeline)
    backend = PipecatDictationBackend("moonshine", _config())

    assert await backend.transcribe(b"one") == "hello there"


@pytest.mark.asyncio
async def test_a_service_that_will_not_build_is_reported_to_whoever_asked(monkeypatch):
    """A missing package fails the preparation, naming the setting that named it.

    The message is the manager's, and it is the difference between "the voice did
    not start" and "the voice did not start because the package that transcribes
    is not installed".
    """

    def create_service(name: str, config: DictationConfig) -> FakeService:
        raise RuntimeError(f"speech service {name!r} needs the 'moonshine_voice' package")

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    backend = PipecatDictationBackend("moonshine", _config())

    with pytest.raises(RuntimeError, match="moonshine_voice"):
        await backend.prepare(lambda _message: None)


@pytest.mark.asyncio
async def test_closing_the_backend_stops_its_pipeline_once(monkeypatch):
    """Letting the backend go stops the worker, and saying it twice is harmless.

    The model is resident until this runs, so a teardown that ran twice, or not
    at all, is a session's memory.
    """
    pipeline = FakePipeline()
    _stub(monkeypatch, [], pipeline)
    backend = PipecatDictationBackend("moonshine", _config())
    await backend.prepare(lambda _message: None)

    await backend.aclose()
    await backend.aclose()

    assert pipeline.closes == 1


@pytest.mark.asyncio
async def test_a_session_that_ends_lets_its_backend_go():
    """A backend holding a model is released when the session is over.

    The scheduling is the part worth pinning. `DictationSession.close` is
    synchronous and a backend's close is not, so the teardown has to reach the
    loop without the session that is already over waiting for it.
    """
    closed: list[bool] = []

    class FakeCloser(AnyDictationBackend):
        async def transcribe(self, audio: bytes) -> str:
            return ""

        async def aclose(self) -> None:
            closed.append(True)

    session = DictationSession(_config())
    session.backend = FakeCloser()
    session.close()
    await asyncio.sleep(0)

    assert closed == [True]


@pytest.mark.asyncio
async def test_closing_a_session_that_never_dictated_builds_nothing(monkeypatch):
    """A session that never opened a microphone does not build a backend to close.

    The backend is built on first use, so a session that only ever typed must not
    be the reason a model is created — which is the point of closing one that was
    never made being free.
    """
    built: list[str] = []
    monkeypatch.setattr(
        "zrb.llm.dictation.feature.get_dictation_backend",
        lambda name, config: built.append(name),
    )
    session = DictationSession(_config())
    session.close()
    await asyncio.sleep(0)

    assert built == []
