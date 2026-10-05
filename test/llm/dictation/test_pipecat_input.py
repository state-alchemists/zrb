"""Stage 1 of the Pipecat migration: pushed audio really reaches the pipeline.

The device is never opened here. What is under test is that zrb can hand its own
captured blocks to a Pipecat pipeline and see them arrive downstream, which is
the precondition for every later stage (ADR-0107).
"""

from __future__ import annotations

import asyncio
import importlib
import logging

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from zrb.llm.dictation.listen import SAMPLE_RATE  # noqa: E402
from zrb.llm.dictation.pipecat_input import (  # noqa: E402
    AudioPipeline,
    AudioTally,
    SpeechMetrics,
    SpeechMetricsRecorder,
    create_speech_metrics_stage,
    is_pipecat_available,
)

# 32 ms of 16 kHz mono 16-bit PCM: what a single captured block is.
CHUNK_BYTES = 1024
CHUNK = b"\x00\x01" * (CHUNK_BYTES // 2)
CHUNK_COUNT = 50

# A block of silence: one 512-sample frame of it, which is what the detector
# analyses at a time.
SILENCE = b"\x00\x00" * (CHUNK_BYTES // 2)


def _sink(pipeline: AudioPipeline) -> AudioTally:
    """The tally the pipeline's far end writes, which is what this file asserts.

    `AudioPipeline.counter` can only be typed as pipecat's `FrameProcessor`,
    because the sink's own class is built inside the factory — importing this
    module must not import pipecat — so the counting it does is read off the
    `AudioTally` it was handed instead.
    """
    return pipeline.tally


async def _settle(predicate, timeout: float = 5.0) -> bool:
    """Wait until `predicate()` holds, or *timeout* elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


@pytest.mark.asyncio
async def test_audio_pushed_from_outside_reaches_the_sink():
    """Every block pushed in is counted at the far end, byte for byte.

    This is the count stage 1 exits on, and it exercises the transport's whole
    reason to exist: pipecat's base `start` never calls `set_transport_ready`,
    which is the call that creates the queue a pushed block is read from, so
    without it the push has nowhere to go and this count is zero.
    """
    pipeline = await AudioPipeline.start()
    try:
        for _ in range(CHUNK_COUNT):
            await pipeline.push(CHUNK)

        counted = _sink(pipeline)
        assert await _settle(
            lambda: counted.bytes_received >= CHUNK_COUNT * CHUNK_BYTES
        ), (
            f"only {counted.bytes_received} of the {CHUNK_COUNT * CHUNK_BYTES} "
            "pushed bytes reached the sink"
        )
        assert counted.bytes_received == CHUNK_COUNT * CHUNK_BYTES
    finally:
        await pipeline.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("sample_rate", [8000, SAMPLE_RATE])
async def test_a_block_is_labeled_with_the_rate_the_pipeline_is_running_at(
    sample_rate,
):
    """A block carries the rate it was captured at, and not this module's default.

    The frame says what its samples mean, and the detector reads them at that
    rate: a block labeled 16 kHz into a pipeline running at another rate is one
    analysed at the wrong speed. `push_audio` labeled every block `SAMPLE_RATE`
    whatever the transport took, so the label is pinned against the transport
    the block goes into, at the default rate and at another.
    """
    pipeline = await AudioPipeline.start(sample_rate=sample_rate)
    labels = []
    hand_over = pipeline.transport.process_frame

    async def remember(frame, direction):
        labels.append(frame.sample_rate)
        await hand_over(frame, direction)

    pipeline.transport.process_frame = remember
    try:
        await pipeline.push(CHUNK)

        assert labels == [sample_rate]
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
async def test_closing_hands_every_block_over_before_it_stops_the_worker(monkeypatch):
    """`close` does not stop the pipeline with a block still in flight.

    `push` only queues a block and the transport takes it from there, so a close
    that stops the worker first drops whatever is still queued: the last blocks
    of a listening, the trailing silence among them, which is silence the
    detector needs to report the end of the segment it closes. Where the stop is
    asked for is the only moment that shows the order, so the far end is read
    there — a burst is pushed with no wait in between, which is the state a
    capture leaves behind when a listening ends.
    """
    pipeline = await AudioPipeline.start()
    for _ in range(CHUNK_COUNT):
        await pipeline.push(CHUNK)

    arrived_at_the_ask = []
    ask_the_worker_to_stop = pipeline.worker.cancel

    async def cancel(*args, **kwargs):
        arrived_at_the_ask.append(_sink(pipeline).bytes_received)
        await ask_the_worker_to_stop(*args, **kwargs)

    monkeypatch.setattr(pipeline.worker, "cancel", cancel)

    await pipeline.close()

    assert arrived_at_the_ask == [CHUNK_COUNT * CHUNK_BYTES]


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
        assert await _settle(lambda: _sink(pipeline).bytes_received >= 5 * CHUNK_BYTES)
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


@pytest.mark.asyncio
async def test_a_start_that_never_comes_up_leaves_no_task_running(monkeypatch):
    """A start that fails stops the worker it had already created (PR #561
    review).

    The worker task is created before the pipeline is known to be up, so a start
    that fails has to end it: otherwise it outlives the failure for the life of
    the event loop, holding Pipecat's resources and logging an exception nobody
    is left to read. The StartFrame is refused here, which is the shape of a
    transport that never comes up: the wait that watches for it is what fails.
    """
    from pipecat.pipeline.task import PipelineWorker

    async def refuse(*args, **kwargs):
        raise RuntimeError("the worker will not take the StartFrame")

    monkeypatch.setattr(PipelineWorker, "queue_frames", refuse)
    before = asyncio.all_tasks()

    with pytest.raises(RuntimeError, match="will not take the StartFrame"):
        await AudioPipeline.start()

    await asyncio.sleep(0)

    assert asyncio.all_tasks() <= before


@pytest.mark.asyncio
async def test_a_runner_failure_before_ready_is_reported_promptly(monkeypatch):
    """A worker that dies before readiness must not look like a slow microphone."""
    from pipecat.pipeline.task import PipelineWorker

    async def fail(*args, **kwargs):
        raise RuntimeError("the worker died before readiness")

    monkeypatch.setattr(PipelineWorker, "run", fail)
    started = asyncio.get_running_loop().time()

    with pytest.raises(RuntimeError, match="died before readiness"):
        await AudioPipeline.start()

    assert asyncio.get_running_loop().time() - started < 1.0


@pytest.mark.asyncio
async def test_a_runner_that_exits_before_ready_does_not_hang(monkeypatch):
    """A worker that exits cleanly still leaves readiness unreachable, so the
    start must give up rather than wait on a readiness that can never come."""
    from pipecat.pipeline.task import PipelineWorker

    async def exit_at_once(*args, **kwargs):
        return None

    monkeypatch.setattr(PipelineWorker, "run", exit_at_once)
    started = asyncio.get_running_loop().time()

    with pytest.raises(RuntimeError, match="before the transport was ready"):
        await AudioPipeline.start()

    assert asyncio.get_running_loop().time() - started < 1.0


@pytest.mark.asyncio
async def test_a_worker_that_refuses_the_cancel_still_ends_the_pipeline(monkeypatch):
    """A teardown that fails still ends the pipeline, and raises nothing (PR #561
    review).

    `close` asks the worker to cancel over the worker's own bus, and a pipeline
    already in trouble can fail that ask. `close` promises never to raise — its
    caller is the listening's `finally`, where an escaping failure ends
    hands-free for the session — so the ask is best-effort and the task driving
    the pipeline is cancelled outright when it did not go through.
    """
    pipeline = await AudioPipeline.start()

    async def refuse(*args, **kwargs):
        raise RuntimeError("the worker will not take the cancel")

    monkeypatch.setattr(pipeline.worker, "cancel", refuse)

    await pipeline.close()

    assert pipeline.runner.done()


@pytest.mark.asyncio
async def test_a_runner_that_will_not_stop_is_named_rather_than_left_silent(
    monkeypatch, caplog
):
    """A runner this close cannot stop is reported, not left to look stopped
    (PR #561 review).

    The deadline is what keeps a teardown from being held up, and a task that
    swallows its cancellation cannot be ended from here at all, so the one thing
    left is to say so. The worker's own task still stops, which is the part the
    listening around it depends on.
    """
    pipeline = await AudioPipeline.start()
    # Reached through `importlib`, not a dotted name: a dotted private name in a
    # test is what the private-access ratchet counts, and the deadline is a
    # constant no public seam exposes.
    pipecat_input = importlib.import_module("zrb.llm.dictation.pipecat_input")
    monkeypatch.setattr(pipecat_input, "_CLOSE_TIMEOUT_SECONDS", 0.05)

    async def stuck() -> None:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            await asyncio.sleep(0.2)
            raise RuntimeError("the runner failed on the way out") from None

    worker_task = pipeline.runner
    pipeline.runner = asyncio.create_task(stuck())

    with caplog.at_level(logging.WARNING):
        await asyncio.wait_for(pipeline.close(), timeout=5)

    assert "The Pipecat pipeline is still running after being cancelled" in caplog.text

    await asyncio.wait({pipeline.runner}, timeout=1)
    assert isinstance(pipeline.runner.exception(), RuntimeError)
    assert worker_task.done()


def test_the_recorder_times_speech_between_its_start_and_its_stop():
    """The number a conversation is tuned on: how long the user spoke."""
    ticks = iter([100.0, 100.5])
    recorder = SpeechMetricsRecorder(clock=lambda: next(ticks))

    recorder.record_speech_started()
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=0.5)


def test_speech_still_open_is_counted_but_not_timed():
    """A segment with no end yet has no length, so it is not in the total.

    A snapshot is read while a listening ends, which can land mid-sentence:
    counting the open segment as zero rather than guessing keeps the total
    from overstating what was heard.
    """
    recorder = SpeechMetricsRecorder(clock=lambda: 5.0)

    recorder.record_speech_started()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=0.0)


def test_a_second_segment_adds_to_the_first():
    ticks = iter([1.0, 1.5, 10.0, 10.25])
    recorder = SpeechMetricsRecorder(clock=lambda: next(ticks))

    recorder.record_speech_started()
    recorder.record_speech_stopped()
    recorder.record_speech_started()
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=2, speech_seconds=0.75)


def test_a_stop_with_no_start_heard_adds_nothing():
    """A stop the recorder never saw begin is not speech this pipeline saw."""
    recorder = SpeechMetricsRecorder(clock=lambda: 1.0)

    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=0, speech_seconds=0.0)


def test_a_duplicate_start_does_not_restart_the_clock():
    """The clock is read once per segment: a second start cannot lose the
    first one's beginning, which would shorten what the user said."""
    ticks = iter([1.0, 1.5])
    recorder = SpeechMetricsRecorder(clock=lambda: next(ticks))

    recorder.record_speech_started()
    recorder.record_speech_started()
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=2, speech_seconds=0.5)


def test_the_summary_reads_as_one_line_for_the_log():
    assert SpeechMetrics(2, 1.5).summary() == "2 speech segment(s), 1.5s of speech"


@pytest.mark.asyncio
async def test_the_metrics_stage_times_the_frames_the_detector_reports():
    """The stage reads the detector's own verdict, so it is driven by the
    frames the detector emits rather than by audio of its own."""
    from pipecat.frames.frames import (
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection

    ticks = iter([2.0, 2.5])
    recorder = SpeechMetricsRecorder(clock=lambda: next(ticks))
    stage = create_speech_metrics_stage(recorder)

    await stage.process_frame(VADUserStartedSpeakingFrame(), FrameDirection.DOWNSTREAM)
    await stage.process_frame(VADUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=0.5)


@pytest.mark.asyncio
async def test_a_speech_frame_pushed_at_the_source_reaches_the_metrics_stage():
    """The metrics stage has to sit downstream of the transport in the running
    pipeline, or the detector's verdict never arrives and every session
    reports silence it did not hear."""
    from pipecat.frames.frames import (
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )

    pipeline = await AudioPipeline.start()
    try:
        await pipeline.worker.queue_frames(
            [VADUserStartedSpeakingFrame(), VADUserStoppedSpeakingFrame()]
        )

        assert await _settle(
            lambda: pipeline.get_speech_metrics().speech_segments == 1
        ), "a speech frame pushed at the source never reached the metrics stage"
    finally:
        await pipeline.close()


@pytest.mark.asyncio
async def test_a_pipeline_fed_silence_reports_no_speech_and_keeps_every_byte():
    """The detector in the pipeline invents no speech out of silence, and
    stands between the capture and the sink without dropping any of it."""
    pipeline = await AudioPipeline.start()
    try:
        for _ in range(20):
            await pipeline.push(SILENCE)

        counter = _sink(pipeline)
        expected = 20 * len(SILENCE)
        assert await _settle(lambda: counter.bytes_received >= expected)
        assert counter.bytes_received == expected
        assert pipeline.get_speech_metrics() == SpeechMetrics(0, 0.0)
    finally:
        await pipeline.close()
