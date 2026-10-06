"""Stage 1 of the Pipecat migration: what the detector heard, and for how long.

The recorder's arithmetic is pinned without a pipeline and without audio, the
stage is driven with the frames Pipecat emits, and the running pipeline is asked
for the metrics a session reports. The transport and the teardown it shares are
`test_pipecat_input.py` (ADR-0107).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from zrb.llm.dictation.listen import SAMPLE_RATE  # noqa: E402
from zrb.llm.dictation.pipecat_input import (  # noqa: E402
    AudioPipeline,
    SpeechMetrics,
    SpeechMetricsRecorder,
    create_speech_metrics_stage,
)

# 32 ms of 16 kHz mono 16-bit PCM: what a single captured block is.
CHUNK_BYTES = 1024
CHUNK = b"\x00\x01" * (CHUNK_BYTES // 2)

# How long one block is, and how many of them a timed segment is made of: a
# little under a second of speech.
BLOCK_SECONDS = (CHUNK_BYTES // 2) / SAMPLE_RATE
SPEECH_BLOCKS = 31


async def _settle(predicate, timeout: float = 5.0) -> bool:
    """Wait until `predicate()` holds, or *timeout* elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


def test_the_recorder_adds_the_audio_measured_while_speech_is_heard():
    """The number a conversation is tuned on: how long the user spoke.

    Added as the audio arrives, so the total does not depend on when the stage
    happened to run."""
    recorder = SpeechMetricsRecorder()

    recorder.record_speech_started()
    recorder.record_audio(0.25)
    recorder.record_audio(0.25)
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=0.5)


def test_audio_outside_a_segment_is_not_silence_the_detector_called_speech():
    """Only what was heard while a segment was open is speech.

    A listening is mostly silence, and the detector is what separates the two:
    timing every block that passes would report the length of the session."""
    recorder = SpeechMetricsRecorder()

    recorder.record_audio(1.0)
    recorder.record_speech_started()
    recorder.record_audio(0.25)
    recorder.record_speech_stopped()
    recorder.record_audio(1.0)

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=0.25)


def test_speech_still_open_is_counted_but_not_timed():
    """A segment with no end yet is not in the total.

    A read taken while a listening is still running lands wherever it lands: the
    audio heard for the open segment stays out of the total, and is added when
    the segment ends or the feed does.
    """
    recorder = SpeechMetricsRecorder()

    recorder.record_speech_started()
    recorder.record_audio(1.0)

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=0.0)


def test_the_recorder_closes_a_segment_the_feed_ended_on():
    """A listening that ended mid-sentence is not reported as no time at all.

    The detector reports a stop only when it hears the silence that ends a
    segment, so one still open when the feed ends never gets a stop; the audio it
    was heard over is all of it there will ever be, and is added."""
    recorder = SpeechMetricsRecorder()

    recorder.record_speech_started()
    recorder.record_audio(1.25)
    recorder.record_feed_ended()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=1, speech_seconds=1.25)


def test_ending_a_feed_with_no_segment_open_adds_nothing():
    """A pipeline closed before the detector heard anything reports nothing."""
    recorder = SpeechMetricsRecorder()

    recorder.record_audio(1.0)
    recorder.record_feed_ended()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=0, speech_seconds=0.0)


def test_a_second_segment_adds_to_the_first():
    recorder = SpeechMetricsRecorder()

    recorder.record_speech_started()
    recorder.record_audio(0.5)
    recorder.record_speech_stopped()
    recorder.record_speech_started()
    recorder.record_audio(0.25)
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=2, speech_seconds=0.75)


def test_a_stop_with_no_start_heard_adds_nothing():
    """A stop the recorder never saw begin is not speech this pipeline saw."""
    recorder = SpeechMetricsRecorder()

    recorder.record_audio(1.0)
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=0, speech_seconds=0.0)


def test_a_duplicate_start_does_not_lose_the_audio_already_measured():
    """A second start cannot drop the first one's audio, which would shorten
    what the user said."""
    recorder = SpeechMetricsRecorder()

    recorder.record_speech_started()
    recorder.record_audio(0.25)
    recorder.record_speech_started()
    recorder.record_audio(0.25)
    recorder.record_speech_stopped()

    assert recorder.get_metrics() == SpeechMetrics(speech_segments=2, speech_seconds=0.5)


def test_the_summary_reads_as_one_line_for_the_log():
    assert (
        SpeechMetrics(2, 1.5).summary() == "2 speech segment(s), 1.5s of detected speech"
    )


@pytest.mark.asyncio
async def test_the_metrics_stage_times_the_audio_the_detector_called_speech():
    """The stage times the audio it is handed, and not the clock it runs on.

    The detector's frames arrive while the pipeline works through what was
    pushed into it, so the interval between two of them as this stage sees them
    is the pipeline's latency: a minute of capture pushed as a burst is worked
    through in milliseconds. What is timed here is the length the frames carry —
    a second of speech is a second of speech however fast it was processed, and
    the silence around it is not speech at all.
    """
    from pipecat.frames.frames import (
        InputAudioRawFrame,
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection

    recorder = SpeechMetricsRecorder()
    stage = create_speech_metrics_stage(recorder)
    block = InputAudioRawFrame(audio=CHUNK, sample_rate=SAMPLE_RATE, num_channels=1)

    await stage.process_frame(block, FrameDirection.DOWNSTREAM)
    await stage.process_frame(VADUserStartedSpeakingFrame(), FrameDirection.DOWNSTREAM)
    for _ in range(SPEECH_BLOCKS):
        await stage.process_frame(block, FrameDirection.DOWNSTREAM)
    await stage.process_frame(VADUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

    metrics = recorder.get_metrics()
    assert metrics.speech_segments == 1
    assert metrics.speech_seconds == pytest.approx(SPEECH_BLOCKS * BLOCK_SECONDS)


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
async def test_a_listening_that_ended_mid_sentence_is_reported_with_its_audio():
    """Closing the pipeline ends the feed, so its last segment still counts.

    A stop is reported only when the detector hears the silence that ends a
    segment, and a listening that stops while the user is still speaking never
    gives it one. The blocks it was heard over were pushed and drained all the
    same, so without the close ending the feed the session would report `1 speech
    segment(s), 0.0s of detected speech` for a sentence it heard in full.
    """
    from pipecat.frames.frames import VADUserStartedSpeakingFrame

    pipeline = await AudioPipeline.start()
    try:
        await pipeline.worker.queue_frames([VADUserStartedSpeakingFrame()])
        assert await _settle(
            lambda: pipeline.get_speech_metrics().speech_segments == 1
        ), "the segment never opened"
        # Pushed and left queued, so only the drain in `close` can measure them.
        for _ in range(SPEECH_BLOCKS):
            await pipeline.push(CHUNK)
    finally:
        await pipeline.close()

    metrics = pipeline.get_speech_metrics()
    assert metrics.speech_segments == 1
    assert metrics.speech_seconds == pytest.approx(SPEECH_BLOCKS * BLOCK_SECONDS)
