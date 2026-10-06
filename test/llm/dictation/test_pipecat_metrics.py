"""Stage 1 of the Pipecat migration: what the detector heard, and for how long.

The recorder's arithmetic is pinned without a pipeline and without audio, the
stage is driven with the frames Pipecat emits, and the running pipeline is asked
for the metrics a session reports. The transport and the teardown it shares are
`test_pipecat_input.py` (ADR-0107).
"""

from __future__ import annotations

import asyncio
import time

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from pipecat.audio.vad.vad_analyzer import VADAnalyzer, VADParams  # noqa: E402
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

#: How many blocks the detector's defaults confirm a verdict over: 0.2s of speech
#: to start a segment, 0.2s of silence to end one, at 32ms a block.
VERDICT_BLOCKS = 6

#: How long one stalled analysis takes — long enough that the block it was
#: decided from has been counted at the far end well before its verdict is
#: pushed, which is what puts a verdict in flight at a teardown.
STALL_SECONDS = 0.5


class _ScriptedAnalyzer(VADAnalyzer):
    """Speech for the first *speech_frames* analysed frames, silence after.

    A stand-in for the model, so a test can point at where the detector's
    verdicts land. The volume bar is lifted: what is under test is the order
    pipecat hands frames over in, not its loudness gate. One block is one
    analysis at 16 kHz, which is what the pipeline runs at here.

    *stall_at* holds one analysis — the one that has analysed *stall_at* frames —
    for `STALL_SECONDS`. The model runs off the event loop, so a stalled analysis
    lets the pipeline carry the block it is working on all the way to the far end
    while the verdict is still being decided.
    """

    def __init__(self, speech_frames: int, stall_at: int | None = None) -> None:
        super().__init__(params=VADParams(min_volume=0.0))
        self._speech_frames = speech_frames
        self._stall_at = stall_at
        self._analysed = 0

    def num_frames_required(self) -> int:
        return 512

    def voice_confidence(self, buffer: bytes) -> float:
        self._analysed += 1
        if self._stall_at is not None and self._analysed >= self._stall_at:
            time.sleep(STALL_SECONDS)
        return 0.9 if self._analysed <= self._speech_frames else 0.0


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


@pytest.mark.asyncio
async def test_the_block_that_ends_a_segment_is_counted_with_it(monkeypatch):
    """The detector hands a block over before the verdict it decided from it.

    `VADProcessor.process_frame` pushes the audio downstream first and runs the
    detector afterwards, so the block that confirms the end of a segment reaches
    the metrics stage while that segment is still open and is counted with it.
    Read the other way round, every segment would lose the silence it ended on.

    What the seconds have to agree with is the blocks the stage was handed
    between the two verdicts, the terminating one included, so the order is read
    at the stage instead of being assumed here.
    """
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.processors.frame_processor import FrameDirection

    handed: list[str] = []
    make_stage = create_speech_metrics_stage

    def recording_stage(recorder):
        stage = make_stage(recorder)
        inner = stage.process_frame

        async def remember(frame, direction):
            if direction == FrameDirection.DOWNSTREAM:
                handed.append(type(frame).__name__)
            await inner(frame, direction)

        stage.process_frame = remember
        return stage

    monkeypatch.setattr(
        "zrb.llm.dictation.pipecat_input.create_voice_activity_detector",
        lambda: VADProcessor(vad_analyzer=_ScriptedAnalyzer(SPEECH_BLOCKS)),
    )
    monkeypatch.setattr(
        "zrb.llm.dictation.pipecat_input.create_speech_metrics_stage", recording_stage
    )

    pipeline = await AudioPipeline.start()
    try:
        # Enough blocks after the scripted speech for the detector to confirm the
        # end: it wants 0.2s of silence, which is six blocks of this size.
        for _ in range(SPEECH_BLOCKS + 12):
            await pipeline.push(CHUNK)
        assert await _settle(lambda: "VADUserStoppedSpeakingFrame" in handed), (
            f"the scripted detector never ended its segment: {handed}"
        )
    finally:
        await pipeline.close()

    started = handed.index("VADUserStartedSpeakingFrame")
    stopped = handed.index("VADUserStoppedSpeakingFrame")
    counted = [
        name for name in handed[started + 1 : stopped] if name == "InputAudioRawFrame"
    ]

    assert handed[stopped - 1] == "InputAudioRawFrame", (
        "the block that ended the segment reached the stage after its verdict"
    )
    # The detector confirms a start after 0.2s of speech and an end after 0.2s of
    # silence — six blocks each at its defaults — so the blocks it was speaking
    # over are exactly the scripted ones, the block it ended on included.
    assert len(counted) == SPEECH_BLOCKS
    assert pipeline.get_speech_metrics().speech_seconds == pytest.approx(
        SPEECH_BLOCKS * BLOCK_SECONDS
    )


@pytest.mark.asyncio
async def test_a_verdict_still_being_decided_is_not_lost_to_the_teardown(monkeypatch):
    """The drain waits on the bytes, and the verdict decided from the last of
    them still arrives (PR #584 review).

    The far end is downstream of the stage that reads the verdicts, so the last
    block handed over is counted before the detector has finished with it — and
    the detector runs its model off the event loop, so this is the ordinary case
    for a model slower than the capture rather than a corner. A teardown that
    stops at the count therefore hands the worker to its cancel with a verdict
    still in flight, and the segment that last block began would be reported as
    no segment at all.

    It is not lost. The verdict is pushed while the block it was decided from is
    still being processed, and a cancel is a system frame that queues behind that
    block, so the verdict is read before the worker stops. The feed ends before
    it — read here off the recorder's own call, so the race this is about is
    entered rather than assumed — and the segment is still reported after it.
    """
    from pipecat.processors.audio.vad_processor import VADProcessor

    monkeypatch.setattr(
        "zrb.llm.dictation.pipecat_input.create_voice_activity_detector",
        lambda: VADProcessor(
            vad_analyzer=_ScriptedAnalyzer(VERDICT_BLOCKS, stall_at=VERDICT_BLOCKS)
        ),
    )

    pipeline = await AudioPipeline.start()
    segments_at_feed_end: list[int] = []
    read_feed_ended = pipeline.recorder.record_feed_ended

    def note_feed_ended() -> None:
        segments_at_feed_end.append(pipeline.get_speech_metrics().speech_segments)
        read_feed_ended()

    monkeypatch.setattr(pipeline.recorder, "record_feed_ended", note_feed_ended)
    try:
        # Exactly the blocks the start verdict is confirmed over, so the block
        # that begins the segment is the last one handed over.
        for _ in range(VERDICT_BLOCKS):
            await pipeline.push(CHUNK)
    finally:
        await pipeline.close()

    assert segments_at_feed_end == [0], (
        "the verdict reached the metrics stage before the feed ended, so this "
        "test is not exercising the teardown it is about"
    )
    assert pipeline.get_speech_metrics().speech_segments == 1
