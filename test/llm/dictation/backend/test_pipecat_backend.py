"""Dictation transcribed by a Pipecat speech-to-text service.

No model is installed here and none is needed. The pipeline is stubbed, because
what is under test is the wiring around it: that the service is built once and
the same pipeline answers every utterance, that a pipeline which has stopped is
replaced rather than kept, and that a backend which is let go of stops what it
started and refuses to start another. A load that does not go through is
`test_pipecat_backend_load.py`; what the pipeline does with an utterance is
`test/llm/dictation/test_pipecat_stt.py`.
"""

from __future__ import annotations

import asyncio


import pytest


from zrb.llm.dictation.backend.pipecat import PipecatDictationBackend
from zrb.llm.dictation.config import DictationConfig

MODULE = "zrb.llm.dictation.backend.pipecat"

# A sample rate to start a stubbed pipeline at; the real one is Pipecat's own.
SAMPLE_RATE = 16000


class FakePipeline:
    """The pipeline a service would be transcribing through."""

    def __init__(self) -> None:
        self.segments: list[bytes] = []
        self.closes = 0
        # Set by a test to stand in for a pipeline that retired itself: one that
        # gave up on a segment whose answer names no segment, and stopped.
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
async def test_a_pipeline_that_has_stopped_is_replaced_for_the_next_segment(
    monkeypatch,
):
    """A session that is still listening is not left with a stopped pipeline.

    A pipeline retires itself when a segment it timed out on is still in the
    service's hands and its answer would be taken for the next segment's. The
    session keeps listening after a failed transcription, so keeping the retired
    pipeline would fail every segment after it — and would keep the model loaded
    behind a pipeline nothing asks anything of.
    """
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
async def test_the_backend_names_the_loop_its_pipeline_runs_on(monkeypatch):
    """The loop a session can be closed from is the one that owns the pipeline.

    A synchronous teardown runs wherever the session was being served, which is
    not necessarily this loop, and a pipeline can only be stopped from its own.
    """
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
    """Nothing builds a second service for a session that is over.

    A recording in flight when the session ends reaches its transcription after
    the backend has been let go. Building a pipeline again for it would leave the
    new one — and its model — running with no session left to close it.
    """
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
    """A backend whose loop is gone still lets its pipeline go.

    `aclose` cannot run once the loop a pipeline was started on has stopped, and
    a session that ends after that has no other way to reach the worker. Holding
    the pipeline anyway is what keeps the service's model — a gigabyte of it, for
    Whisper — resident behind a reference the session has already dropped, so the
    backend lets go of it, and refuses to start a second one for a session over.
    """
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
