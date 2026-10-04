"""Stage 1 of the Pipecat migration: pushed audio really reaches the pipeline.

The device is never opened here. What is under test is that zrb can hand its own
captured blocks to a Pipecat pipeline and see them arrive downstream, which is
the precondition for every later stage (ADR-0106).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from zrb.llm.dictation.pipecat_input import (  # noqa: E402
    create_audio_counter,
    create_input_transport,
    push_audio,
)

# 32 ms of 16 kHz mono 16-bit PCM: what a single captured block is.
CHUNK_BYTES = 1024
CHUNK = b"\x00\x01" * (CHUNK_BYTES // 2)
CHUNK_COUNT = 50


def _build_pipeline():
    """`transport -> counter`, running, plus the pieces the test needs.

    `PipelineWorker`, not the `PipelineTask` alias: the alias is deprecated since
    pipecat 1.3.0 and removed in 2.0.0, and this is new code (ADR-0106).

    A worker does not start itself — `run` is the coroutine that drives the
    pipeline — so the session owns that task, exactly as the migration will have
    to.
    """
    from pipecat.frames.frames import StartFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineWorker
    from pipecat.utils.asyncio.task_manager import TaskManager
    from pipecat.workers.base_worker import WorkerParams

    transport = create_input_transport()
    counter = create_audio_counter()
    worker = PipelineWorker(Pipeline([transport, counter]))
    runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
    return worker, runner, transport, counter, StartFrame


async def _shutdown(worker, runner) -> None:
    """Stop the pipeline and wait for its task to unwind."""
    await worker.cancel()
    try:
        await asyncio.wait_for(runner, timeout=5)
    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
        pass


async def _settle(predicate, timeout: float = 5.0) -> bool:
    """Wait until `predicate()` holds, or `timeout` elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


@pytest.mark.asyncio
async def test_audio_pushed_from_outside_reaches_the_sink():
    """Every block pushed in comes out the far end, in order and intact.

    This is the count stage 1 exits on, and it exercises the subclass's whole
    reason to exist: pipecat's base `start` never calls `set_transport_ready`,
    which is the call that creates the queue a pushed block is read from, so
    without the override this count is zero.
    """
    worker, runner, transport, counter, StartFrame = _build_pipeline()
    try:
        await worker.queue_frames([StartFrame()])
        assert await _settle(lambda: counter.frame_count >= 1), (
            "the pipeline never came up: no frame reached the sink"
        )

        for _ in range(CHUNK_COUNT):
            await push_audio(transport, CHUNK)

        assert await _settle(lambda: len(counter.audio_frames) >= CHUNK_COUNT), (
            f"only {len(counter.audio_frames)} of {CHUNK_COUNT} pushed blocks "
            "reached the sink"
        )
        assert counter.bytes_received == CHUNK_COUNT * CHUNK_BYTES
        assert [frame.audio for frame in counter.audio_frames] == [CHUNK] * CHUNK_COUNT
    finally:
        await _shutdown(worker, runner)


@pytest.mark.asyncio
async def test_the_pipeline_shares_the_already_running_loop():
    """The pipeline must not need an event loop of its own.

    A chat session already owns one, so a second loop would be a redesign rather
    than a drop-in. A coroutine ticking alongside the pipeline proves the loop is
    shared: it keeps advancing while the pipeline is alive and draining audio.
    """
    worker, runner, transport, counter, StartFrame = _build_pipeline()
    ticks = 0
    ticking = True

    async def tick() -> None:
        nonlocal ticks
        while ticking:
            await asyncio.sleep(0.005)
            ticks += 1

    ticker = asyncio.create_task(tick())
    try:
        await worker.queue_frames([StartFrame()])
        assert await _settle(lambda: counter.frame_count >= 1)
        for _ in range(5):
            await push_audio(transport, CHUNK)
        assert await _settle(lambda: len(counter.audio_frames) >= 5)
        assert ticks > 0, "the pipeline starved the loop it was started in"
    finally:
        ticking = False
        await ticker
        await _shutdown(worker, runner)
