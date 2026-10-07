"""The service a load built, and who lets go of it.

`prepare` loads a model off the loop and hands it to a pipeline, and there are
three ways that ends with a service and no pipeline around it: the load is
cancelled, the start around it fails, or the load lands after the loop that was
waiting for it is gone. Each leaves a loaded service nobody answers through, and
a service holds its model — a gigabyte of it, for Whisper — so each is a leak
unless the service is closed.

What a load that works does — one service, one pipeline, every utterance
answered through them — is `test_pipecat_backend.py`. Like it, this file carries
its own copy of the doubles: a test file is a feature group, not a library.
"""

from __future__ import annotations

import asyncio
import threading

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


async def _until(predicate, timeout: float = 5.0) -> None:
    """Yield to the loop until *predicate* holds, or fail saying it never did."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate() and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert predicate(), "the condition never held"


@pytest.mark.asyncio
async def test_a_service_that_will_not_build_is_reported_to_whoever_asked(monkeypatch):
    """A missing package fails the preparation, naming the setting that named it.

    The message is the manager's, and it is the difference between "the voice did
    not start" and "the voice did not start because the package that transcribes
    is not installed".
    """

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
    """A session that ends while its service is still loading lets go of what that
    load starts.

    `prepare` loads the model and the teardown lets the backend go; the two can
    overlap, because the load is off the loop and the teardown is not. Run that
    way, the teardown finds no pipeline to close — so the one the load starts
    afterwards is the only thing holding a worker and a resident model, and it
    has to be the load that lets it go.
    """
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
    """A model that finished loading for nobody is cleaned up, not dropped.

    The constructor is in a thread of its own, so cancelling `prepare` stops the
    wait and nothing else: the model still finishes loading. Nobody will start a
    pipeline around that service, so the service is what has to be let go of —
    and a registered one may hold more in its own constructor than the model the
    collector gets to whenever it gets to it.
    """
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
    """A service whose loop is gone is closed, not left to the collector.

    Cancelling stops the wait and nothing else, so the model can arrive after the
    loop it was being waited on is already closed. Letting the service go is still
    the whole point of the orphan path there: the loop that closed is the
    session's, not necessarily the process's, so its model would stay resident for
    however long the process has left.

    Runs on a loop of its own rather than pytest's, because this case *is* a loop
    closed before the load lands, and pytest's is still running.
    """
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
    """A service built for a pipeline that then fails is closed, not dropped.

    `prepare` owns the service from the moment its load returns until a pipeline
    has adopted it. A start that raises would otherwise drop a loaded model with
    the session still running: the load ran on a thread of its own, so no other
    part of the session holds a reference to what it built.
    """
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
    """Ownership passes to the pipeline, so a start that works closes nothing.

    The service belongs to the pipeline from the moment one has it, and a
    `prepare` that closed it anyway would take the model out from under the
    pipeline about to be handed every segment of the session.
    """
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
