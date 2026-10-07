"""Tests cleanup when Pipecat service loading cannot produce a pipeline."""

from __future__ import annotations

import asyncio
import threading

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


async def _until(predicate, timeout: float = 5.0) -> None:
    """Yield to the loop until *predicate* holds, or fail saying it never did."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate() and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert predicate(), "the condition never held"


@pytest.mark.asyncio
async def test_a_service_that_will_not_build_is_reported_to_whoever_asked(monkeypatch):
    """A missing service package names the configured dependency."""

    def create_service(name: str, config: DictationConfig) -> FakeService:
        raise RuntimeError(
            f"speech service {name!r} needs the 'moonshine_voice' package"
        )

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    backend = PipecatDictationBackend("moonshine", _config())

    with pytest.raises(RuntimeError, match="moonshine_voice"):
        await backend.prepare(lambda _message: None)


@pytest.mark.asyncio
async def test_a_teardown_while_the_model_loads_leaves_no_pipeline(monkeypatch):
    """Teardown during loading closes the pipeline created after teardown starts."""
    pipeline = FakePipeline()
    loading = threading.Event()
    reached = threading.Event()

    def create_service(name: str, config: DictationConfig) -> FakeService:
        reached.set()
        assert loading.wait(5)  # the model load the teardown interrupts
        return FakeService()

    async def start(service: FakeService, sample_rate: int = SAMPLE_RATE):
        return pipeline

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    monkeypatch.setattr(f"{MODULE}.STTPipeline.start", start)

    backend = PipecatDictationBackend("moonshine", _config())
    preparing = asyncio.create_task(backend.prepare(lambda _message: None))
    # The load runs in its own thread, so yielding is what lets it reach the gate.
    deadline = asyncio.get_running_loop().time() + 5
    while not reached.is_set() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)

    assert reached.is_set(), "the model was never loaded"
    await backend.aclose()
    loading.set()

    with pytest.raises(RuntimeError, match="was let go"):
        await preparing

    assert pipeline.closes == 1
    assert backend.owner_loop is None  # nothing left to close on a loop


@pytest.mark.asyncio
async def test_cancelled_service_loading_uses_a_daemon_thread(monkeypatch):
    """A blocked model constructor must not keep interpreter shutdown alive."""
    loading = threading.Event()
    reached = threading.Event()
    daemon_flags: list[bool] = []

    def create_service(name: str, config: DictationConfig) -> FakeService:
        daemon_flags.append(threading.current_thread().daemon)
        reached.set()
        loading.wait(5)
        return FakeService()

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    backend = PipecatDictationBackend("moonshine", _config())
    preparing = asyncio.create_task(backend.prepare(lambda _message: None))

    try:
        deadline = asyncio.get_running_loop().time() + 5
        while not reached.is_set() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        assert reached.is_set(), "the model was never loaded"

        preparing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await preparing

        assert daemon_flags == [True]
    finally:
        loading.set()


@pytest.mark.asyncio
async def test_a_load_that_outlives_a_cancelled_prepare_is_let_go(monkeypatch):
    """A service finishing after cancellation is cleaned up without a pipeline."""
    reached = threading.Event()
    release = threading.Event()
    built: list[FakeService] = []

    def create_service(name: str, config: DictationConfig) -> FakeService:
        reached.set()
        release.wait(5)  # the model load a cancelled prepare walks away from
        service = FakeService()
        built.append(service)
        return service

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    backend = PipecatDictationBackend("moonshine", _config())
    preparing = asyncio.create_task(backend.prepare(lambda _message: None))

    try:
        await _until(reached.is_set)

        preparing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await preparing

        release.set()
        await _until(lambda: bool(built) and built[0].cleanups == 1)

        assert built[0].cleanups == 1
    finally:
        release.set()


def test_a_load_that_lands_after_its_loop_closed_is_still_let_go(monkeypatch):
    """A service arriving after its loop closes is still cleaned up."""
    reached = threading.Event()
    release = threading.Event()
    threads: list[threading.Thread] = []
    built: list[FakeService] = []

    def create_service(name: str, config: DictationConfig) -> FakeService:
        threads.append(threading.current_thread())
        reached.set()
        assert release.wait(5)  # the load a cancelled prepare walked away from
        service = FakeService()
        built.append(service)
        return service

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    backend = PipecatDictationBackend("moonshine", _config())

    async def prepare() -> None:
        await backend.prepare(lambda _message: None)

    loop = asyncio.new_event_loop()
    try:
        preparing = loop.create_task(prepare())
        loop.run_until_complete(_until(reached.is_set))
        preparing.cancel()
        with pytest.raises(asyncio.CancelledError):
            loop.run_until_complete(preparing)
    finally:
        loop.close()

    release.set()
    worker = threads[0]
    worker.join(5)

    assert not worker.is_alive(), "the load never landed"
    assert [service.cleanups for service in built] == [1]


@pytest.mark.asyncio
async def test_a_pipeline_that_cannot_be_started_lets_the_service_go(monkeypatch):
    """A failed pipeline start closes the service still owned by `prepare`."""
    built: list[FakeService] = []

    def create_service(name: str, config: DictationConfig) -> FakeService:
        service = FakeService()
        built.append(service)
        return service

    async def start(service: FakeService, sample_rate: int = SAMPLE_RATE):
        raise RuntimeError("Pipecat refused the pipeline")

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    monkeypatch.setattr(f"{MODULE}.STTPipeline.start", start)
    backend = PipecatDictationBackend("moonshine", _config())

    with pytest.raises(RuntimeError, match="refused"):
        await backend.prepare(lambda _message: None)

    assert [service.cleanups for service in built] == [1]
    assert backend.owner_loop is None


@pytest.mark.asyncio
async def test_a_service_a_started_pipeline_adopted_is_not_closed(monkeypatch):
    """A started pipeline owns its service, so `prepare` does not close it."""
    pipeline = FakePipeline()
    built: list[FakeService] = []

    def create_service(name: str, config: DictationConfig) -> FakeService:
        service = FakeService()
        built.append(service)
        return service

    async def start(service: FakeService, sample_rate: int = SAMPLE_RATE):
        return pipeline

    monkeypatch.setattr(f"{MODULE}.stt_manager.create_service", create_service)
    monkeypatch.setattr(f"{MODULE}.STTPipeline.start", start)
    backend = PipecatDictationBackend("moonshine", _config())

    await backend.prepare(lambda _message: None)

    assert [service.cleanups for service in built] == [0]
    assert await backend.transcribe(b"one") == "hello there"
