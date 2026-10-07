"""A Pipecat pipeline that transcribes the utterances zrb has already cut.

This is the stage that puts a *speech-to-text service* behind dictation, so the
service a config names (`zrb.llm.voice`) is what zrb listens through.

What crosses the boundary is a segment and its transcript, and nothing else.
zrb still decides where an utterance begins and ends — `listen.UtteranceCutter`
cuts it — so the pipeline is handed a finished segment and told, in Pipecat's
own terms, that speech spanned it; the service answers with a
`TranscriptionFrame`. The guards that read that transcript (wake words, stop
words, approvals) never move, which is the point: a service can be swapped
under them without changing what a user's words mean.

The pipeline outlives one utterance, because the expensive part is the model.
Whisper and Moonshine both load theirs inside the service's constructor, so
building a pipeline per utterance would pay for the model per utterance.
"""

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

#: How many bytes of audio one pushed frame carries: 32 ms of 16 kHz mono
#: 16-bit PCM, which is the span Pipecat's voice-activity detection analyses at
#: a time. A segment goes in as several of these rather than as one frame, so a
#: long one is not a single large wait on the way in.
SEGMENT_BLOCK_BYTES = 1024

#: How long one segment may take to come back before it is given up on. A large
#: model on a slow machine is the case this bounds, so it is deliberately
#: generous: the point is not to hurry a transcription along but to stop a
#: pipeline that has stopped answering from holding a listening open forever.
_TRANSCRIBE_TIMEOUT_SECONDS = 120.0

#: How long the worker may take to unwind once it has been told to stop.
_CLOSE_TIMEOUT_SECONDS = 5.0


def _iter_blocks(audio: bytes) -> Iterator[bytes]:
    """*audio* as the frames a segment is fed in: `SEGMENT_BLOCK_BYTES` apiece.

    The last block is whatever is left rather than padded out, because the
    service buffers what it is given and decides for itself what silence to add
    before it transcribes (`trailing_silence_secs`). Padding here would hand the
    model silence zrb never captured.
    """
    for start in range(0, len(audio), SEGMENT_BLOCK_BYTES):
        yield audio[start : start + SEGMENT_BLOCK_BYTES]


class TranscriptionTimeout(RuntimeError):
    """A segment the service did not answer within the transcription timeout.

    Its own type rather than a plain `RuntimeError`, because the pipeline does
    more with it than report it: a segment given up on this way is still being
    transcribed, and the answer it is still owed would otherwise be read as the
    answer to whatever segment is asked for next (`STTPipeline.transcribe`).
    """


class TranscriptRecorder:
    """What the service reported about one segment, and nothing else.

    Plain Python, so the accounting is testable without a pipeline and readable
    from outside the sink that writes it: a sink cannot report anything the
    recorder has no method for, which is what keeps the pipeline's frame
    vocabulary from leaking into the session that waits on it.

    One segment is answered by one transcript, so `expect_segment` is called
    before the audio goes in and the outcome read after the stop: a transcript
    nobody waited on would otherwise answer the segment after it. A worker that
    has stopped is *not* cleared that way, because a pipeline that is gone does
    not come back — the next segment would wait out the whole timeout to learn
    what the recorder already knows.
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
        """A failure the service reported, as an `ErrorFrame` carries it.

        Recorded rather than logged: a failed transcription is an answer for
        the segment that was pushed, and the caller that asked for it is the one
        that knows whether the session goes on.
        """
        self._failure = message
        self._arrived.set()

    def record_stopped(self, reason: str) -> None:
        """The worker stopped: no transcript can arrive for any segment."""
        self._is_stopped = True
        self._stop_reason = reason
        self._arrived.set()

    async def wait(self, timeout: float) -> str:
        """The transcript for the segment being waited on.

        Ends when the service answers, when the worker that would have carried
        the answer is known to have stopped, or at *timeout*. Raises rather than
        returning a placeholder: a transcription that never came is not a
        transcript of an empty utterance, and the words a session acts on are
        not something to invent. A *timeout* is a type of its own
        (`TranscriptionTimeout`), because giving up on a segment is not the end
        of the matter for the pipeline that was handed it (`_retire`).

        A worker that has stopped is asked about before the wait and not after
        it: `expect_segment` has just cleared the arrival, so a pipeline known to
        be gone would otherwise be waited on for the whole timeout.
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
    """Make *service* answer for a segment it found no words in, too.

    A segmented service yields a `TranscriptionFrame` only when it has text to
    put in one, so a segment it heard nothing in produces no frame at all — and
    a caller waiting for one waits until its own timeout, which is minutes.
    Nothing pushed after the segment can stand in for "that transcription is
    over": the service transcribes out of band, in a task of its own, behind the
    frame path. The one call that *is* over is the transcription, so that is
    what is wrapped.

    Two of Pipecat's frames look like the signal and are not. Its
    `MetricsFrame` for a finished processing window is pushed from inside the
    transcription, one step *before* the transcript, and a system frame outranks
    the data frame behind it — so a reader would answer "no words" and drop the
    words. `VADUserStoppedSpeakingFrame` is forwarded as soon as the segment is
    handed over, long before it is transcribed.

    This is the adapter layer ADR-0107 says the guards cost: Pipecat answers what
    media event happened, and that an empty transcript is the answer is zrb's
    reading of it, because zrb is the side that reads a transcript as an
    utterance. It is also what keeps a session from hanging: zrb's guards drop a
    transcript with no words in it, and a dropped transcript must arrive as
    promptly as a kept one.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import TranscriptionFrame
    from pipecat.utils.time import time_now_iso8601

    original = service.run_stt

    async def run_stt(audio: bytes) -> "AsyncGenerator[Frame | None, None]":
        # A `TranscriptionFrame` is the answer; no other frame is. The metrics
        # frame pushed one step before the transcript, and the system frame that
        # outranks it, both arrive in a segment that *was* transcribed, so
        # reading either as the answer would swallow the words behind it and
        # answer "no words" for a segment that has some.
        answered = False
        async for frame in original(audio):
            if isinstance(frame, TranscriptionFrame):
                answered = True
            yield frame
        if not answered:
            yield TranscriptionFrame("", "", time_now_iso8601())

    service.run_stt = run_stt


def create_transcript_sink(recorder: TranscriptRecorder) -> FrameProcessor:
    """A pipeline sink that hands every transcript it sees to *recorder*.

    It reads Pipecat's frames and decides nothing: a `TranscriptionFrame` is a
    transcript, and every other frame passes through untouched. Nothing is
    translated into a decision here — whether a transcript is meant for zrb at
    all is the session's question, asked from the words.

    A failure is deliberately not read here. A service that fails reports it
    through `push_error`, which travels *upstream*, and a sink at the far end of
    the pipeline is the one place that will never see it; the service's own
    `on_error` is where that is caught (`STTPipeline.start`).
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
    """A running Pipecat pipeline whose service transcribes zrb's segments.

    It is handed a finished utterance and answers with the words spoken in it:
    `transcribe` pushes the audio between the two frames a segmented service
    reads its boundaries from — `VADUserStartedSpeakingFrame` and
    `VADUserStoppedSpeakingFrame` — and waits for the `TranscriptionFrame` the
    service pushes back.

    Those are the frames a detector would have emitted, and zrb emits them
    because zrb is where this boundary was decided: `UtteranceCutter` cut this
    audio before the pipeline ever saw it. The detector takes that job over only
    once its own boundaries have been shown to match on recorded audio
    (`docs/architecture/3-peripheral-flow/voice-on-pipecat.md`, stage 2), and
    until then feeding it a segment zrb has already cut would be two cutters
    disagreeing about one utterance.

    There is deliberately no input transport. A `BaseInputTransport` is what
    reads a device, and zrb keeps the device; it would also reorder what is
    pushed through it, because it queues `InputAudioRawFrame` for a task of its
    own to forward while passing every other system frame straight on — so the
    stop that ends a segment would overtake the segment. Going in through the
    worker's push queue keeps one path, and therefore one order, for the audio
    and for the boundaries that frame it.
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
        # One segment at a time: the recorder answers one wait with one
        # transcript, so a second segment pushed while the first is still being
        # transcribed would take the answer meant for it.
        self._segment_lock = asyncio.Lock()
        # Set once this pipeline has been stopped: it transcribes nothing more,
        # and whoever holds it starts another rather than hand it a segment.
        self._is_closed = False

    @property
    def service(self) -> "STTService":
        """The service this pipeline transcribes through."""
        return self._service

    @property
    def is_closed(self) -> bool:
        """Whether this pipeline has been stopped, and transcribes nothing more.

        Asked by whoever holds one before handing over a segment: a pipeline that
        retired itself — a segment it gave up on, whose answer names no segment —
        is not one a session can be answered through (`_retire`).

        Nor is one whose worker stopped with nobody asking it to. Pipecat ends one
        on a frame a processor pushes upstream, or on a failure its run task does
        not survive, and neither goes through `close` — the run task *is* the
        worker, so its end is read here rather than waited for. A holder that kept
        such a pipeline would hand it every segment to come and be told "the
        Pipecat worker stopped" for the rest of the session.
        """
        return self._is_closed or self._runner.done()

    @classmethod
    async def start(
        cls, service: "STTService", sample_rate: int = SAMPLE_RATE
    ) -> "STTPipeline":
        """Start a pipeline around *service* on the running loop, ready to use.

        The service arrives already built, because building it is the caller's
        once-only cost: a manager's `create_service` is what loads the model,
        and this is where the result is put to work. A worker does not start
        itself — `run` is the coroutine that drives it — so the pipeline owns
        that task.
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
            """Report a failure the service pushed.

            A transcription that raises is caught by the service itself, which
            pushes the failure *upstream* and leaves the pipeline running — so
            the sink downstream never sees it, and without this the segment it
            belonged to would wait out the whole timeout to learn nothing is
            coming.

            Every event handler takes the object that raised it first, which is
            the service here, and this one has no use for it
            (`pipecat.utils.base_object.BaseObject._run_handler`).
            """
            recorder.record_failure(error.error)

        service.add_event_handler("on_error", on_service_error)

        def on_worker_stopped(task: "asyncio.Task[None]") -> None:
            """Report the worker stopping, so a segment waiting on it is not left waiting.

            Every frame travels through the worker, so once it has stopped no
            transcript can arrive. Saying so here is what turns a pipeline that
            died mid-session into a failed transcription, instead of a listening
            that sits silent until the timeout runs out.

            A done callback rather than a task watching the worker: the failure
            is read off the task as it ends, which is also what stops the loop
            from reporting it later as never retrieved, and there is nothing
            left to cancel at a teardown.
            """
            reason = "the Pipecat worker stopped"
            if not task.cancelled() and task.exception() is not None:
                reason = f"{reason}: {task.exception()}"
            recorder.record_stopped(reason)

        worker = PipelineWorker(
            Pipeline([service, sink]),
            # Idle is this pipeline's normal state, not a fault. It outlives one
            # utterance — that is the point of keeping it — so it sits with no
            # frames between them, and Pipecat's watchdog would take it away for
            # that: its `idle_timeout_secs` defaults to 300s, armed by the last
            # `TranscriptionFrame`, after which it cancels the worker and every
            # later segment fails with "the Pipecat worker stopped". `None`
            # leaves the monitor off entirely; zrb closes this pipeline itself,
            # from the backend's `aclose`.
            idle_timeout_secs=None,
            # The service reads the rate for the frames that carry none of their
            # own, and it reaches it through the worker's params. Pipecat's
            # `TaskManager` binds to the loop this runs on, so no second loop is
            # created for a pipeline started from a running one.
            params=PipelineParams(audio_in_sample_rate=sample_rate),
        )
        runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
        runner.add_done_callback(on_worker_stopped)
        return cls(worker, runner, service, sink, recorder, sample_rate)

    async def transcribe(self, audio: bytes) -> str:
        """The text spoken in *audio*: 16 kHz mono 16-bit PCM, one utterance.

        Raises rather than guessing when the service does not answer. An empty
        segment is refused outright: there is no audio to transcribe, and a
        service handed only silence answers with what it hears in silence,
        which is not a transcript of anything the user said. A segment the
        service leaves unanswered past the timeout retires the pipeline: the
        service is still transcribing it, and its answer would be taken for the
        next segment's (`_retire`).
        """
        if not audio:
            raise ValueError("a Pipecat segment needs audio to transcribe")
        async with self._segment_lock:
            # A pipeline that is already gone would take the frames and answer
            # with nothing, leaving this segment to wait out the whole timeout;
            # the worker's own end is the shorter answer.
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
        """Stop a pipeline that has a segment it can no longer account for.

        The segment the wait just gave up on is still being transcribed, and a
        `TranscriptionFrame` names no segment: the recorder can tell one answer
        from another only by the order they arrive in, so that answer would be
        read as the answer to whatever segment is asked for next — a user's
        previous words taken for their current ones.

        Pipecat offers no per-segment fix for that. An `InterruptionFrame` only
        resets the service's own TTFB state, and cancelling the service's segment
        task would leave it with nothing to transcribe with for the rest of the
        session. What does stop a transcription in flight is the pipeline's own
        cancel, so the pipeline is what goes; the backend that holds it starts
        another one for the segment after
        (`PipecatDictationBackend.prepare`), because a session that is still
        listening is better served by a working pipeline than by a pipeline that
        would fail every segment to come.
        """
        await self.close()

    async def _push_segment(self, audio: bytes) -> None:
        """Push one segment: its boundaries, and its audio between them.

        The start comes first, and not as a formality. A segmented service
        buffers audio while it believes the user is speaking, and keeps only the
        last second of it while it believes they are not — so a segment pushed
        without the start would be trimmed to its own tail before the stop that
        transcribes it arrived, and the transcript would be of the end of the
        sentence.
        """
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
        """Stop the pipeline and wait, briefly, for its worker to unwind.

        Never raises: this runs in a session's teardown, where an escaping
        failure would end voice for the session rather than end a pipeline. A
        worker still going after the wait is cancelled; one that swallows that
        is logged and left. `asyncio.wait`, not `wait_for`, so a worker that had
        already failed is not raised a second time here — whoever pushed its
        last frame has seen it — and its exception is read off so the loop does
        not log it as never retrieved.

        The pipeline counts as stopped from here on, whether or not the worker
        went quietly: nothing more is handed to it (`is_closed`).
        """
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
