"""Tests Pipecat backend lifecycle and pipeline reuse."""

from __future__ import annotations

import asyncio


import pytest


from zrb.llm.dictation.backend.pipecat import PipecatDictationBackend
from zrb.llm.dictation.config import DictationConfig

MODULE = "zrb.llm.dictation.backend.pipecat"

# Pipecat's sample rate for the stubbed pipeline.
SAMPLE_RATE = 16000


class FakePipeline:
    """The pipeline a service would be transcribing through."""

    def __init__(self) -> None:
        self.segments: list[bytes] = []
        self.closes = 0
        # Simulates a pipeline retired after a timed-out segment.
        self.is_closed = False

    async def transcribe(self, audio: bytes) -> str:
        self.segments.append(audio)
        return "hello there"

    async def close(self) -> None:
        self.closes += 1


class FakeService:
    """A service, as far as this file is concerned: something to build, and
    something Pipecat's own `cleanup` can be called on to let go of."""

    def __init__(self) -> None:
        self.cleanups = 0

    async def cleanup(self) -> None:
        self.cleanups += 1


def _config(**kwargs) -> DictationConfig:
    return DictationConfig(**kwargs).resolve()


def _stub(monkeypatch, built: list[str], pipeline: FakePipeline) -> None:
    """Stubs model loading and worker startup for wiring tests."""

    def create_service(name: str, config: DictationConfig) -> FakeService:
        built.append(name)
        return FakeService()

    async def start(service: FakeService, sample_rate: int = SAMPLE_RATE):
        return pipeline

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    monkeypatch.setattr(f"{MODULE}.STTPipeline.start", start)


@pytest.mark.asyncio
async def test_the_service_is_built_once_and_answers_every_utterance(monkeypatch):
    """Repeated preparation reuses one model and pipeline."""
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
async def test_a_pipeline_that_has_stopped_is_replaced_for_the_next_segment(
    monkeypatch,
):
    """A retired pipeline is replaced before the next segment."""
    pipelines = [FakePipeline(), FakePipeline()]
    started: list[FakePipeline] = []
    built: list[str] = []

    def create_service(name: str, config: DictationConfig) -> FakeService:
        built.append(name)
        return FakeService()

    async def start(service: FakeService, sample_rate: int = SAMPLE_RATE):
        pipeline = pipelines[len(started)]
        started.append(pipeline)
        return pipeline

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    monkeypatch.setattr(f"{MODULE}.STTPipeline.start", start)
    backend = PipecatDictationBackend("moonshine", _config())
    await backend.prepare(lambda _message: None)
    assert await backend.transcribe(b"one") == "hello there"

    pipelines[0].is_closed = True  # it retired itself on a segment that timed out
    assert await backend.transcribe(b"two") == "hello there"

    assert built == ["moonshine", "moonshine"]
    assert started == pipelines
    assert pipelines[1].segments == [b"two"]


@pytest.mark.asyncio
async def test_the_backend_is_named_after_the_service_it_was_built_from():
    """A message says which service answered, not only that Pipecat did."""
    backend = PipecatDictationBackend("whisper", _config())
    assert backend.name == "Pipecat (whisper)"


@pytest.mark.asyncio
async def test_transcribing_without_preparing_still_transcribes(monkeypatch):
    """Transcribing without `prepare` lazily starts a pipeline."""
    pipeline = FakePipeline()
    _stub(monkeypatch, [], pipeline)
    backend = PipecatDictationBackend("moonshine", _config())

    assert await backend.transcribe(b"one") == "hello there"


@pytest.mark.asyncio
async def test_closing_the_backend_stops_its_pipeline_once(monkeypatch):
    """Closing stops the worker once and is idempotent."""
    pipeline = FakePipeline()
    _stub(monkeypatch, [], pipeline)
    backend = PipecatDictationBackend("moonshine", _config())
    await backend.prepare(lambda _message: None)

    await backend.aclose()
    await backend.aclose()

    assert pipeline.closes == 1


@pytest.mark.asyncio
async def test_the_backend_names_the_loop_its_pipeline_runs_on(monkeypatch):
    """The backend records the pipeline's owning loop for teardown."""
    pipeline = FakePipeline()
    _stub(monkeypatch, [], pipeline)
    backend = PipecatDictationBackend("moonshine", _config())
    assert backend.owner_loop is None  # nothing started yet

    await backend.prepare(lambda _message: None)

    assert backend.owner_loop is asyncio.get_running_loop()

    await backend.aclose()

    assert backend.owner_loop is None


@pytest.mark.asyncio
async def test_a_backend_that_was_let_go_is_not_started_again(monkeypatch):
    """A released backend does not rebuild a service for late audio."""
    pipeline = FakePipeline()
    built: list[str] = []
    _stub(monkeypatch, built, pipeline)
    backend = PipecatDictationBackend("moonshine", _config())
    await backend.prepare(lambda _message: None)
    await backend.aclose()

    with pytest.raises(RuntimeError, match="let go"):
        await backend.transcribe(b"one")

    assert built == ["moonshine"]
    assert pipeline.closes == 1
    assert pipeline.segments == []


@pytest.mark.asyncio
async def test_a_released_backend_lets_its_pipeline_go_for_good(monkeypatch):
    """A released backend drops its unreachable pipeline and refuses restart."""
    pipeline = FakePipeline()
    _stub(monkeypatch, [], pipeline)
    backend = PipecatDictationBackend("moonshine", _config())
    await backend.prepare(lambda _message: None)

    backend.release()

    assert backend.owner_loop is None
    assert pipeline.closes == 0  # the worker cannot be reached to stop it
    with pytest.raises(RuntimeError, match="let go"):
        await backend.transcribe(b"one")
    assert pipeline.segments == []
