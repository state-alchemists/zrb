"""Pipecat transcribes a cut utterance whole and reports failed pipelines."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from pipecat.frames.frames import (  # noqa: E402
    EndWorkerFrame,
    Frame,
    MetricsFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402
from pipecat.services.settings import STTSettings  # noqa: E402
from pipecat.services.stt_service import SegmentedSTTService  # noqa: E402
from pipecat.utils.time import time_now_iso8601  # noqa: E402

from zrb.llm.dictation import pipecat_stt  # noqa: E402
from zrb.llm.dictation.listen import SAMPLE_RATE  # noqa: E402
from zrb.llm.dictation.pipecat_stt import (  # noqa: E402
    STTPipeline,
    TranscriptRecorder,
)

#: SegmentedSTTService appends half a second so models hear the last word's end.
TRAILING_SILENCE_BYTES = int(SAMPLE_RATE * 0.5) * 2

#: A 10 ms captured block.
BLOCK = b"\x00\x01" * (SAMPLE_RATE // 100)

#: Exceeds the service's one-second tail, pinning truncation of long utterances.
UTTERANCE = b"\x01\x02" * int(SAMPLE_RATE * 1.2)

ANSWER = "hello there"


class FakeSegmentedService(SegmentedSTTService):
    """Answers raw PCM because local services disable WAV wrapping."""

    def __init__(self) -> None:
        # Explicit settings avoid validation errors for uninitialized fields.
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
    """Yields no frame when the model finds no words."""

    ANSWERS = False

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        if self.ANSWERS:
            yield TranscriptionFrame(ANSWER, "", time_now_iso8601())


class MetricsFirstSegmentedService(FakeSegmentedService):
    """Reports metrics before words, so readers must skip `MetricsFrame`."""

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        yield MetricsFrame([])
        yield TranscriptionFrame(ANSWER, "", time_now_iso8601())


class MetricsOnlySegmentedService(FakeSegmentedService):
    """Reports only metrics when the model finds no words."""

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        yield MetricsFrame([])


class HeldSegmentedService(FakeSegmentedService):
    """Holds the first segment so its late answer cannot answer the next."""

    def __init__(self) -> None:
        super().__init__()
        self.hold = asyncio.Event()

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        self.segments.append(audio)
        if len(self.segments) == 1:
            await self.hold.wait()
        yield TranscriptionFrame(f"words {len(self.segments)}", "", time_now_iso8601())


@pytest.mark.asyncio
async def test_a_cut_utterance_reaches_the_service_whole_and_its_text_comes_back():
    """Boundary frames keep a cut segment whole; without them Pipecat trims it to its tail."""
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
    """A long-lived pipeline loads the model once and answers each segment."""
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
    """Rejects empty audio instead of transcribing its padding silence."""
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
    """A closed pipeline fails immediately instead of waiting for the timeout."""
    pipeline = await STTPipeline.start(FakeSegmentedService())
    await pipeline.close()

    with pytest.raises(RuntimeError, match="Pipecat worker stopped"):
        await pipeline.transcribe(UTTERANCE)


@pytest.mark.asyncio
async def test_a_worker_that_stopped_on_its_own_leaves_the_pipeline_closed():
    """`EndWorkerFrame` marks a worker gone so later segments fail immediately."""
    service = FakeSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        assert not pipeline.is_closed

        await service.push_frame(EndWorkerFrame(), FrameDirection.UPSTREAM)

        # The worker marks itself closed over several loop turns.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5
        while not pipeline.is_closed and loop.time() < deadline:
            await asyncio.sleep(0.01)
        assert pipeline.is_closed
    finally:
        await pipeline.close()


@pytest.mark.asyncio
async def test_a_transcription_that_fails_is_reported_to_whoever_asked():
    """A model failure reaches the caller waiting for that segment."""
    service = RaisingSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        with pytest.raises(RuntimeError, match="transcription failed"):
            await pipeline.transcribe(UTTERANCE)
    finally:
        await pipeline.close()


@pytest.mark.asyncio
async def test_a_segment_with_no_words_in_it_is_answered_at_once():
    """No transcript frame means an immediate empty answer, not a frozen listener."""
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
    """A metrics-only response is an immediate empty answer, not a pending transcript."""
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
async def test_a_timed_out_segment_is_not_answered_by_the_one_after_it(monkeypatch):
    """Retiring a timed-out pipeline prevents its late transcript answering the next segment."""
    monkeypatch.setattr(pipecat_stt, "_TRANSCRIBE_TIMEOUT_SECONDS", 0.05)
    service = HeldSegmentedService()
    pipeline = await STTPipeline.start(service)
    try:
        with pytest.raises(pipecat_stt.TranscriptionTimeout):
            await pipeline.transcribe(UTTERANCE)

        assert pipeline.is_closed
        # The held answer has no waiter and cannot answer the next segment.
        service.hold.set()
        with pytest.raises(RuntimeError, match="Pipecat worker stopped"):
            await pipeline.transcribe(UTTERANCE)
    finally:
        await pipeline.close()

    assert service.segments == [UTTERANCE + bytes(TRAILING_SILENCE_BYTES)]


@pytest.mark.asyncio
async def test_a_transcript_that_never_comes_times_out_instead_of_being_invented():
    """A missing transcript times out as an error, not an empty answer."""
    recorder = TranscriptRecorder()
    recorder.expect_segment()

    with pytest.raises(RuntimeError, match="did not transcribe"):
        await recorder.wait(0.05)


@pytest.mark.asyncio
async def test_a_stopped_worker_is_remembered_across_the_segments_after_it():
    """A stopped worker remains a known failure instead of being rediscovered by timeout."""
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
    """Small frames are reassembled into the complete long utterance."""
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
    """Teardown ends worker tasks and remains safe to repeat."""
    pipeline = await STTPipeline.start(FakeSegmentedService())
    await pipeline.transcribe(UTTERANCE)
    await pipeline.close()
    await pipeline.close()

    pending = [task for task in asyncio.all_tasks() if not task.done()]
    assert pending == [asyncio.current_task()]
