"""Stage 1 of the Pipecat migration: pushed audio really reaches the pipeline.

The device is never opened here. What is under test is that zrb can hand its own
captured blocks to a Pipecat pipeline and see them arrive downstream, which is
the precondition for every later stage (ADR-0106).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from zrb.llm.dictation.pipecat_input import (  # noqa: E402
    AudioPipeline,
    is_pipecat_available,
)

# 32 ms of 16 kHz mono 16-bit PCM: what a single captured block is.
CHUNK_BYTES = 1024
CHUNK = b"\x00\x01" * (CHUNK_BYTES // 2)
CHUNK_COUNT = 50


def _sink(pipeline: AudioPipeline) -> Any:
    """The pipeline's sink, with the count it keeps.

    `AudioPipeline.counter` can only be typed as pipecat's `FrameProcessor`,
    because the sink's own class is built inside the factory — importing this
    module must not import pipecat. Its `frame_count`, `bytes_received` and
    `audio_frames` are what stage 1 counts on, and what this file asserts.
    """
    return pipeline.counter


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

    This is the count stage 1 exits on, and it exercises the transport's whole
    reason to exist: pipecat's base `start` never calls `set_transport_ready`,
    which is the call that creates the queue a pushed block is read from, so
    without it the push has nowhere to go and this count is zero.
    """
    pipeline = await AudioPipeline.start()
    try:
        for _ in range(CHUNK_COUNT):
            await pipeline.push(CHUNK)

        counter = _sink(pipeline)
        assert await _settle(lambda: len(counter.audio_frames) >= CHUNK_COUNT), (
            f"only {len(counter.audio_frames)} of {CHUNK_COUNT} pushed blocks "
            "reached the sink"
        )
        assert counter.bytes_received == CHUNK_COUNT * CHUNK_BYTES
        assert [frame.audio for frame in counter.audio_frames] == [CHUNK] * CHUNK_COUNT
    finally:
        await pipeline.close()


@pytest.mark.asyncio
async def test_closing_the_pipeline_leaves_no_task_running():
    """`start` and `close` leave the loop as they found it.

    A session opens the pipeline for its listening and closes it after, so a
    worker left running would outlive the microphone it was fed from.
    """
    pipeline = await AudioPipeline.start()

    await pipeline.close()

    assert pipeline.runner.done()


@pytest.mark.asyncio
async def test_the_pipeline_shares_the_already_running_loop():
    """The pipeline must not need an event loop of its own.

    A chat session already owns one, so a second loop would be a redesign rather
    than a drop-in. A coroutine ticking alongside the pipeline proves the loop is
    shared: it keeps advancing while the pipeline is alive and draining audio.
    """
    pipeline = await AudioPipeline.start()
    ticks = 0
    ticking = True

    async def tick() -> None:
        nonlocal ticks
        while ticking:
            await asyncio.sleep(0.005)
            ticks += 1

    ticker = asyncio.create_task(tick())
    try:
        for _ in range(5):
            await pipeline.push(CHUNK)
        assert await _settle(lambda: len(_sink(pipeline).audio_frames) >= 5)
        assert ticks > 0, "the pipeline starved the loop it was started in"
    finally:
        ticking = False
        await ticker
        await pipeline.close()


def test_pipecat_availability_follows_the_installed_extra(monkeypatch):
    """The capture path asks this before it builds a pipeline, so an install
    without the extra must not pay for the voice stack: it is answered without
    importing pipecat."""
    assert is_pipecat_available()

    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)

    assert not is_pipecat_available()
