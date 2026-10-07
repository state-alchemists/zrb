"""A Pipecat pipeline that transcribes utterances zrb has already cut.

The configured speech-to-text service receives each finished segment and returns
a `TranscriptionFrame`; wake-word, stop-word and approval guards stay unchanged.
The pipeline outlives one utterance because Whisper and Moonshine load their
models in the service constructor."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

from zrb.llm.dictation.listen import SAMPLE_RATE
from zrb.llm.util.teardown import cancel_and_wait, close_quietly

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pipecat.frames.frames import ErrorFrame, Frame
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.services.stt_service import STTService

logger = logging.getLogger(__name__)

__all__ = [
    "SEGMENT_BLOCK_BYTES",
    "STTPipeline",
    "TranscriptRecorder",
    "TranscriptionTimeout",
    "answer_every_segment",
    "create_transcript_sink",
]

#: 32 ms of 16 kHz mono 16-bit PCM, the span Pipecat's VAD analyses at a time.
#: Segments are fed as several blocks so a long one is not a single large wait.
SEGMENT_BLOCK_BYTES = 1024

#: Bounds slow models and prevents an unresponsive pipeline holding a session open.
_TRANSCRIBE_TIMEOUT_SECONDS = 120.0

#: How long the worker may take to unwind once it has been told to stop.
_CLOSE_TIMEOUT_SECONDS = 5.0


def _iter_blocks(audio: bytes) -> Iterator[bytes]:
    """*audio* split into `SEGMENT_BLOCK_BYTES` frames without padding.

    The service adds its own trailing silence; padding would give it silence zrb
    never captured (`trailing_silence_secs`).
    """
    for start in range(0, len(audio), SEGMENT_BLOCK_BYTES):
        yield audio[start : start + SEGMENT_BLOCK_BYTES]


class TranscriptionTimeout(RuntimeError):
    """A segment the service did not answer within the transcription timeout.

    The pipeline retires after this because the late answer could be read as the
    next segment's transcript (`STTPipeline.transcribe`).
    """


class TranscriptRecorder:
    """Records one segment's transcript or failure without exposing Pipecat frames.

    `expect_segment` clears the previous outcome before audio is pushed; stopped
    workers remain signalled so the next segment fails without waiting.
    """

    def __init__(self) -> None:
        self._text: str | None = None
        self._failure: str | None = None
        self._is_stopped = False
        self._stop_reason = ""
        self._arrived = asyncio.Event()

    @property
    def is_stopped(self) -> bool:
        """Whether the worker behind this recorder has stopped for good."""
        return self._is_stopped

    @property
    def stop_reason(self) -> str:
        """Why the worker stopped, once it has; empty while it is still running."""
        return self._stop_reason

    def expect_segment(self) -> None:
        """Start waiting for the next segment, forgetting the last outcome."""
        self._text = None
        self._failure = None
        self._arrived.clear()

    def record_transcript(self, text: str) -> None:
        """The service's transcript for the segment being waited on."""
        self._text = text
        self._arrived.set()

    def record_failure(self, message: str) -> None:
        """Record the failure carried by an `ErrorFrame` for the waiting segment."""
        self._failure = message
        self._arrived.set()

    def record_stopped(self, reason: str) -> None:
        """The worker stopped: no transcript can arrive for any segment."""
        self._is_stopped = True
        self._stop_reason = reason
        self._arrived.set()

    async def wait(self, timeout: float) -> str:
        """Return the segment transcript or raise for failure, stop or timeout.

        A stopped worker is checked before waiting because `expect_segment` clears
        the arrival event; a late answer would belong to the next segment, so a
        timeout retires the pipeline (`_retire`).
        """
        if not self._is_stopped and not self._arrived.is_set():
            try:
                await asyncio.wait_for(self._arrived.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise TranscriptionTimeout(
                    f"the Pipecat service did not transcribe the segment within "
                    f"{timeout:g}s"
                ) from None
        if self._failure is not None:
            raise RuntimeError(self._failure)
        if self._is_stopped:
            raise RuntimeError(self._stop_reason or "the Pipecat worker stopped")
        if self._text is None:
            raise RuntimeError("the Pipecat service reported an empty transcript")
        return self._text


def answer_every_segment(service: "STTService") -> None:
    """Make *service* emit an empty `TranscriptionFrame` for silent segments.

    Segmented services emit no frame without text, so callers would wait for the
    timeout. `MetricsFrame`, system frames and `VADUserStoppedSpeakingFrame` are
    not transcript boundaries; wrapping the service's transcription completion
    avoids treating them as empty answers (ADR-0107).
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import TranscriptionFrame
    from pipecat.utils.time import time_now_iso8601

    original = service.run_stt

    async def run_stt(audio: bytes) -> "AsyncGenerator[Frame | None, None]":
        # Only `TranscriptionFrame` answers; metrics and system frames can precede
        # it and would otherwise swallow a non-empty transcript.
        answered = False
        async for frame in original(audio):
            if isinstance(frame, TranscriptionFrame):
                answered = True
            yield frame
        if not answered:
            yield TranscriptionFrame("", "", time_now_iso8601())

    service.run_stt = run_stt


def create_transcript_sink(recorder: TranscriptRecorder) -> FrameProcessor:
    """Record `TranscriptionFrame` objects and pass every frame through.

    Service failures travel upstream through `push_error`, so `STTPipeline.start`
    handles them rather than this downstream sink.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import TranscriptionFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class TranscriptSink(FrameProcessor):
        """Records the service's transcript, and decides nothing about it."""

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, TranscriptionFrame):
                recorder.record_transcript(frame.text)
            await self.push_frame(frame, direction)

    return TranscriptSink()


class STTPipeline:
    """A running Pipecat pipeline that transcribes zrb's finished segments.

    `transcribe` pushes audio between `VADUserStartedSpeakingFrame` and
    `VADUserStoppedSpeakingFrame`, then waits for `TranscriptionFrame`. zrb emits
    those boundaries because `UtteranceCutter` already cut the audio; detector
    ownership waits for recorded-audio validation (`voice-on-pipecat.md`, stage 2).
    No input transport is used: its separate audio task could let the stop frame
    overtake the segment, while the worker queue preserves one ordering path.
    """

    def __init__(
        self,
        worker: "PipelineWorker",
        runner: "asyncio.Task[None]",
        service: "STTService",
        sink: "FrameProcessor",
        recorder: TranscriptRecorder,
        sample_rate: int,
    ) -> None:
        self._worker = worker
        self._runner = runner
        self._service = service
        self._sink = sink
        self._recorder = recorder
        self._sample_rate = sample_rate
        # One transcript answers one wait; concurrent segments could take each
        # other's answers.
        self._segment_lock = asyncio.Lock()
        # A stopped pipeline accepts no more segments.
        self._is_closed = False

    @property
    def service(self) -> "STTService":
        """The service this pipeline transcribes through."""
        return self._service

    @property
    def is_closed(self) -> bool:
        """Whether this pipeline has stopped and cannot transcribe more segments.

        A retired pipeline or a worker whose run task ended must be replaced before
        another segment is handed to it.
        """
        return self._is_closed or self._runner.done()

    @classmethod
    async def start(
        cls, service: "STTService", sample_rate: int = SAMPLE_RATE
    ) -> "STTPipeline":
        """Start a pipeline around an already-built *service* on the running loop.

        `create_service` pays the model-loading cost; this method owns the worker's
        `run` task.
        """
        # lazy: heavy third-party — pipecat is the `voice` extra.
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.worker import PipelineParams, PipelineWorker
        from pipecat.utils.asyncio.task_manager import TaskManager
        from pipecat.workers.base_worker import WorkerParams

        recorder = TranscriptRecorder()
        sink = create_transcript_sink(recorder)
        answer_every_segment(service)

        def on_service_error(_service: "STTService", error: "ErrorFrame") -> None:
            """Record an upstream service failure for the waiting segment.

            The handler receives the service first and does not use it
            (`BaseObject._run_handler`)."""
            recorder.record_failure(error.error)

        service.add_event_handler("on_error", on_service_error)

        def on_worker_stopped(task: "asyncio.Task[None]") -> None:
            """Record worker termination so waiting segments fail immediately.

            Reading the exception in the done callback prevents an unretrieved-task
            warning."""
            reason = "the Pipecat worker stopped"
            if not task.cancelled() and task.exception() is not None:
                reason = f"{reason}: {task.exception()}"
            recorder.record_stopped(reason)

        worker = PipelineWorker(
            Pipeline([service, sink]),
            # The pipeline idles between segments; Pipecat's default 300s watchdog
            # would cancel it, so zrb closes it from the backend's `aclose`.
            idle_timeout_secs=None,
            # The worker supplies the sample rate to frames that lack one and
            # binds `TaskManager` to the running loop.
            params=PipelineParams(audio_in_sample_rate=sample_rate),
        )
        runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
        runner.add_done_callback(on_worker_stopped)
        return cls(worker, runner, service, sink, recorder, sample_rate)

    async def transcribe(self, audio: bytes) -> str:
        """Return the transcript of one 16 kHz mono 16-bit PCM utterance.

        Empty audio is rejected; a timeout retires the pipeline because its late
        answer could be read as the next segment's (`_retire`)."""
        if not audio:
            raise ValueError("a Pipecat segment needs audio to transcribe")
        async with self._segment_lock:
            # A stopped worker cannot answer; fail without waiting for the timeout.
            if self._runner.done() or self._recorder.is_stopped:
                raise RuntimeError(
                    self._recorder.stop_reason or "the Pipecat worker stopped"
                )
            self._recorder.expect_segment()
            await self._push_segment(audio)
            try:
                return await self._recorder.wait(_TRANSCRIBE_TIMEOUT_SECONDS)
            except TranscriptionTimeout:
                await self._retire()
                raise

    async def _retire(self) -> None:
        """Stop a pipeline whose timed-out segment could answer the next one.

        Pipecat has no per-segment cancellation; cancelling the pipeline stops the
        in-flight transcription, and `PipecatDictationBackend.prepare` replaces it.
        """
        await self.close()

    async def _push_segment(self, audio: bytes) -> None:
        """Push one segment between its start and stop boundaries.

        The start is required because segmented services trim audio captured
        before speech; without it, the transcript would contain only the tail."""
        # lazy: heavy third-party — pipecat is the `voice` extra.
        from pipecat.frames.frames import (
            InputAudioRawFrame,
            VADUserStartedSpeakingFrame,
            VADUserStoppedSpeakingFrame,
        )

        await self._worker.queue_frame(VADUserStartedSpeakingFrame())
        for block in _iter_blocks(audio):
            await self._worker.queue_frame(
                InputAudioRawFrame(
                    audio=block, sample_rate=self._sample_rate, num_channels=1
                )
            )
        await self._worker.queue_frame(VADUserStoppedSpeakingFrame())

    async def close(self) -> None:
        """Stop the pipeline without raising during session teardown.

        A worker still running after `_CLOSE_TIMEOUT_SECONDS` is cancelled; its
        exception is read so the loop does not report it as unretrieved."""
        self._is_closed = True
        await close_quietly(self._worker.cancel, "the Pipecat worker")
        done, _ = await asyncio.wait({self._runner}, timeout=_CLOSE_TIMEOUT_SECONDS)
        if not done:
            done = await cancel_and_wait(
                self._runner, "The Pipecat pipeline", _CLOSE_TIMEOUT_SECONDS
            )
        for task in done:
            if not task.cancelled():
                task.exception()
