"""Slice 2 of the Pipecat migration: a cut utterance, transcribed by a service.

No model is installed here and none is needed. What is under test is the pipeline
zrb drives: that an utterance zrb has already cut reaches the service whole, that
its transcript comes back to whoever asked for it, and that a pipeline which has
failed is reported rather than waited on. A `SegmentedSTTService` that answers
without a model stands in for Moonshine, Whisper and FunASR, which all transcribe
a finished segment the same way — the service is Pipecat's, and so is the shape
under test.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from pipecat.frames.frames import Frame, MetricsFrame, TranscriptionFrame  # noqa: E402
from pipecat.services.settings import STTSettings  # noqa: E402
from pipecat.services.stt_service import SegmentedSTTService  # noqa: E402
from pipecat.utils.time import time_now_iso8601  # noqa: E402

from zrb.llm.dictation.listen import SAMPLE_RATE  # noqa: E402
from zrb.llm.dictation.pipecat_stt import (  # noqa: E402
    STTPipeline,
    TranscriptRecorder,
)

#: The silence a segmented service appends to a segment before it transcribes
#: it: `SegmentedSTTService`'s own default of half a second, which is what makes
#: a model hear the end of the last word rather than a hard cut.
TRAILING_SILENCE_BYTES = int(SAMPLE_RATE * 0.5) * 2

#: A captured block as `listen` produces it, and as this pipeline is fed.
BLOCK = b"\x00\x01" * (SAMPLE_RATE // 100)  # 10 ms

#: An utterance longer than the one second of audio a segmented service keeps
#: while it believes nobody is speaking. A shorter one would arrive whole either
#: way, which is exactly the failure this file exists to catch.
UTTERANCE = b"\x01\x02" * int(SAMPLE_RATE * 1.2)

ANSWER = "hello there"


class FakeSegmentedService(SegmentedSTTService):
    """A segmented service that answers from its buffer instead of a model.

    It takes its segments the way the local services zrb registers do: raw
    16-bit PCM, not a WAV container. `SegmentedSTTService` wraps a segment in a
    WAV header by default, which is what a cloud upload API wants; Moonshine,
    Whisper and FunASR all override `wants_wav_segments` to be handed the
    buffer itself, so a fake that did not would be testing a shape zrb never
    builds.
    """

    def __init__(self) -> None:
        # Named rather than left NOT_GIVEN: pipecat's settings validation logs
        # an error for a field its service never initialized.
        super().__init__(
            sample_rate=SAMPLE_RATE, settings=STTSettings(model=None, language=None)
        )
        self.segments: list[bytes] = []

    @property
    def wants_wav_segments(self) -> bool:
        return False

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        """Keep the segment that was buffered, and answer with a fixed text."""
        self.segments.append(audio)
        yield TranscriptionFrame(ANSWER, "", time_now_iso8601())


class RaisingSegmentedService(FakeSegmentedService):
    """A segmented service whose transcription fails, as a real model can."""

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        if audio:
            # `if`, not a bare raise: the yield below is what makes this an
            # async generator, and code after a `raise` cannot be reached to
            # say so.
            raise RuntimeError("the model is unhappy")
        yield TranscriptionFrame(ANSWER, "", time_now_iso8601())


class SilentSegmentedService(FakeSegmentedService):
    """A segmented service that finds no words in what it was buffered.

    Moonshine, Whisper and FunASR all yield their transcript only when they have
    one, so a segment full of a cough, a door, or a language the model does not
    know produces no frame at all. This is what that looks like.
    """

    ANSWERS = False

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        if self.ANSWERS:
            yield TranscriptionFrame(ANSWER, "", time_now_iso8601())


class MetricsFirstSegmentedService(FakeSegmentedService):
    """A service that reports a metric for its window, then its words.

    Pipecat pushes a `MetricsFrame` from inside the transcription, one step
    *before* the transcript, and a system frame outranks the data frame behind
    it. A reader that took any frame for the answer would drop the words.
    """

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        yield MetricsFrame([])
        yield TranscriptionFrame(ANSWER, "", time_now_iso8601())


class MetricsOnlySegmentedService(FakeSegmentedService):
    """A service that reports a metric for its window and no words at all.

    The same frame a real service pushes before a transcript, from a segment
    that had none — a cough, a door, a language the model does not know.
    """

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        yield MetricsFrame([])


@pytest.mark.asyncio
async def test_a_cut_utterance_reaches_the_service_whole_and_its_text_comes_back():
    """The segment zrb cut is what the service transcribes, all of it.

    This is the reason the pipeline is driven with Pipecat's own speech
    boundary frames. A segmented service buffers audio only while it believes
    the user is speaking and keeps the last second of it while it believes they
    are not, so an utterance pushed without that start would arrive trimmed to
    its own tail and the transcript would be of the end of a sentence.
    """
    service = FakeSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        text = await pipeline.transcribe(UTTERANCE)
    finally:
        await pipeline.close()

    assert text == ANSWER
    assert service.segments == [UTTERANCE + bytes(TRAILING_SILENCE_BYTES)]


@pytest.mark.asyncio
async def test_the_pipeline_transcribes_one_utterance_after_another():
    """The pipeline outlives the utterance, so a model is loaded once.

    Whisper and Moonshine both load their model inside the service's
    constructor, which is the cost this pipeline is long-lived to avoid paying
    per utterance; that the second segment is answered at all is what shows the
    recorder did not keep the first answer either.
    """
    service = FakeSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        first = await pipeline.transcribe(UTTERANCE)
        second = await pipeline.transcribe(UTTERANCE)
    finally:
        await pipeline.close()

    assert first == ANSWER
    assert second == ANSWER
    assert len(service.segments) == 2


@pytest.mark.asyncio
async def test_an_utterance_with_no_audio_is_refused_rather_than_transcribed():
    """A segment with no sound in it is a caller's mistake, not a transcript.

    A service handed only the silence it pads a segment with answers with what
    it hears in that silence, and the words a session acts on are not something
    to make up out of nothing.
    """
    service = FakeSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        with pytest.raises(ValueError):
            await pipeline.transcribe(b"")
    finally:
        await pipeline.close()

    assert service.segments == []


@pytest.mark.asyncio
async def test_a_pipeline_that_has_stopped_is_reported_rather_than_waited_on():
    """A closed pipeline fails the segment at once, not at the deadline.

    The frames go into a queue the worker would have drained, so a pipeline that
    is already gone would take the audio and answer with nothing — and a
    listening would sit silent until the transcription timeout ran out.
    """
    pipeline = await STTPipeline.start(FakeSegmentedService())
    await pipeline.close()

    with pytest.raises(RuntimeError, match="Pipecat worker stopped"):
        await pipeline.transcribe(UTTERANCE)


@pytest.mark.asyncio
async def test_a_transcription_that_fails_is_reported_to_whoever_asked():
    """A failing model fails its segment, and the caller is the one told.

    The service catches a raising `run_stt` itself and pushes the failure
    *upstream*, where a sink at the far end of the pipeline would never see it,
    so the segment that was waiting on that transcription is what has to be
    answered — with the failure, since there is no transcript.
    """
    service = RaisingSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        with pytest.raises(RuntimeError, match="transcription failed"):
            await pipeline.transcribe(UTTERANCE)
    finally:
        await pipeline.close()


@pytest.mark.asyncio
async def test_a_segment_with_no_words_in_it_is_answered_at_once():
    """A segment the service finds nothing in is answered, and answered promptly.

    The services yield a transcript only when they have one, so a cough, a door
    or a language the model does not know produces no frame at all. Waiting for
    one that is never coming is a listening that looks frozen for minutes; the
    honest answer is that there were no words, and zrb's own guards already drop
    a transcript with none.
    """
    service = SilentSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        text = await asyncio.wait_for(pipeline.transcribe(UTTERANCE), timeout=5)
    finally:
        await pipeline.close()

    assert text == ""
    assert service.segments == [UTTERANCE + bytes(TRAILING_SILENCE_BYTES)]


@pytest.mark.asyncio
async def test_a_metric_with_no_words_behind_it_is_answered_at_once():
    """A metric is not an answer: a segment it is all there is of is empty.

    The frame Pipecat pushes before a transcript is pushed for a segment with
    none just as readily. Reading it as the answer leaves the caller waiting for
    a transcript that is never coming, which is the same frozen listening the
    empty answer exists to prevent.
    """
    service = MetricsOnlySegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        text = await asyncio.wait_for(pipeline.transcribe(UTTERANCE), timeout=5)
    finally:
        await pipeline.close()

    assert text == ""
    assert service.segments == [UTTERANCE + bytes(TRAILING_SILENCE_BYTES)]


@pytest.mark.asyncio
async def test_a_metric_before_a_transcript_does_not_swallow_its_words():
    """The words behind the metric are still the segment's answer."""
    service = MetricsFirstSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        text = await asyncio.wait_for(pipeline.transcribe(UTTERANCE), timeout=5)
    finally:
        await pipeline.close()

    assert text == ANSWER


@pytest.mark.asyncio
async def test_a_transcript_that_never_comes_times_out_instead_of_being_invented():
    """One segment in, one transcript out; no answer is an error, not an empty one."""
    recorder = TranscriptRecorder()
    recorder.expect_segment()

    with pytest.raises(RuntimeError, match="did not transcribe"):
        await recorder.wait(0.05)


@pytest.mark.asyncio
async def test_a_stopped_worker_is_remembered_across_the_segments_after_it():
    """A pipeline that is gone does not come back, so it is not re-learned.

    `expect_segment` clears the outcome of the segment before, because a
    transcript nobody waited on must not answer the next one. The worker having
    stopped is not that kind of outcome: forgetting it would cost the next
    segment the whole timeout to learn what is already known.
    """
    recorder = TranscriptRecorder()
    recorder.record_stopped("the worker is gone")
    recorder.expect_segment()

    with pytest.raises(RuntimeError, match="the worker is gone"):
        await recorder.wait(0.05)


@pytest.mark.asyncio
async def test_each_segment_is_answered_by_its_own_transcript():
    """Two segments in a row are answered in turn, not by the same answer."""
    recorder = TranscriptRecorder()
    recorder.expect_segment()
    recorder.record_transcript("the first")
    assert await recorder.wait(1.0) == "the first"

    recorder.expect_segment()
    recorder.record_transcript("the second")
    assert await recorder.wait(1.0) == "the second"


@pytest.mark.asyncio
async def test_a_segment_of_any_length_arrives_whole():
    """A long utterance is fed in blocks and reassembled by the service.

    A listening holds minutes of speech, and the frames are small so that no
    single one of them is a large wait on the way in; what the service buffers
    has to be all of it regardless.
    """
    long_utterance = BLOCK * 30
    service = FakeSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        await pipeline.transcribe(long_utterance)
    finally:
        await pipeline.close()

    assert service.segments == [long_utterance + bytes(TRAILING_SILENCE_BYTES)]


@pytest.mark.asyncio
async def test_closing_a_pipeline_leaves_no_task_behind():
    """The teardown ends the worker and the watcher, and is safe to repeat.

    A session that closes a voice pipeline closes it while the chat goes on, so
    a task left running is a task nothing will ever collect.
    """
    pipeline = await STTPipeline.start(FakeSegmentedService())
    await pipeline.transcribe(UTTERANCE)
    await pipeline.close()
    await pipeline.close()

    pending = [task for task in asyncio.all_tasks() if not task.done()]
    assert pending == [asyncio.current_task()]
