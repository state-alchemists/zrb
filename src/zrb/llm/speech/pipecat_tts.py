"""Saying zrb's sentences through a Pipecat text-to-speech service.

Pipecat synthesizes; zrb owns sentence order, interruption, and playback.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections.abc import Iterator
from typing import TYPE_CHECKING, TypeVar

from zrb.config.config import CFG
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.util.teardown import cancel_and_wait, close_quietly

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from pipecat.frames.frames import ErrorFrame, Frame
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.services.tts_service import TTSService

logger = logging.getLogger(__name__)

__all__ = [
    "FIRST_CHUNK_TIMEOUT_SECONDS",
    "SpeechRecorder",
    "SpokenSentence",
    "TTSPipeline",
    "create_speech_sink",
]

#: Maximum wait for a sentence's first audio chunk.
FIRST_CHUNK_TIMEOUT_SECONDS = 30.0

#: Maximum wait for pipeline shutdown.
_TIMEOUT_SECONDS = 5.0

#: Maximum silence before a stalled sentence ends.
_SILENCE_TIMEOUT_SECONDS = 60.0

_T = TypeVar("_T")


class _End:
    """The end of one sentence's audio, optionally with its failure."""

    def __init__(self, problem: str | None = None) -> None:
        self.problem = problem


class SpokenSentence:
    """One sentence's queued audio and completion state."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[bytes | _End]" = queue.Queue()
        self._sample_rate = 0
        self._is_open = True

    @property
    def sample_rate(self) -> int:
        """The rate the service rendered at, once its first chunk has arrived."""
        return self._sample_rate

    @property
    def is_open(self) -> bool:
        """Whether anyone is still reading this sentence's audio."""
        return self._is_open

    def heard_audio(self, audio: bytes, sample_rate: int) -> None:
        """One chunk the service made of this sentence."""
        if not self._is_open:
            return
        if not self._sample_rate:
            self._sample_rate = sample_rate
        self._queue.put(audio)

    def heard_end(self) -> None:
        """The service said this sentence is over: what it made is all of it."""
        if self._is_open:
            self._queue.put(_End())

    def heard_failure(self, problem: str) -> None:
        """The service failed: what it made is all this sentence will be."""
        if self._is_open:
            self._queue.put(_End(problem))

    def close(self) -> None:
        """End the read now: the rest of this sentence's audio is not wanted."""
        if self._is_open:
            self._is_open = False
            self._queue.put(_End())

    def wait_for_chunk(self, timeout: float) -> bytes:
        """Return the first chunk or raise if none arrives."""
        item = self._take(timeout)
        if isinstance(item, _End):
            raise RuntimeError(item.problem or "the Pipecat service said nothing")
        return item

    def take(self, timeout: float) -> "bytes | _End":
        """Return the next chunk or a timeout failure."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return _End(
                f"the Pipecat service made no audio for {timeout:g}s while it was "
                "still saying the sentence"
            )

    def _take(self, timeout: float) -> "bytes | _End":
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(
                f"the Pipecat service said nothing within {timeout:g}s"
            ) from None


class SpeechRecorder:
    """Tracks the sentence currently receiving pipeline output."""

    def __init__(self) -> None:
        self._sentence: SpokenSentence | None = None
        self._is_stopped = False
        self._stop_reason = ""

    def start_sentence(self) -> SpokenSentence:
        """The sentence about to be asked for, whose answers arrive from now on."""
        if self._is_stopped:
            raise RuntimeError(self._stop_reason or "the Pipecat worker stopped")
        self._sentence = SpokenSentence()
        return self._sentence

    def record_audio(self, audio: bytes, sample_rate: int) -> None:
        sentence = self._sentence
        if sentence is not None:
            sentence.heard_audio(audio, sample_rate)

    def record_end(self) -> None:
        sentence = self._sentence
        if sentence is not None:
            sentence.heard_end()

    def record_failure(self, problem: str) -> None:
        sentence = self._sentence
        if sentence is not None:
            sentence.heard_failure(problem)

    def record_stopped(self, reason: str) -> None:
        """The pipeline stopped: no audio can arrive for any sentence again."""
        self._is_stopped = True
        self._stop_reason = reason
        sentence = self._sentence
        if sentence is not None:
            sentence.heard_failure(reason)


def create_speech_sink(recorder: SpeechRecorder) -> FrameProcessor:
    """Create a sink that records Pipecat audio and completion frames."""
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStoppedFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class SpeechSink(FrameProcessor):
        """Records service audio without applying playback policy."""

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, TTSAudioRawFrame):
                recorder.record_audio(frame.audio, frame.sample_rate)
            elif isinstance(frame, TTSStoppedFrame):
                recorder.record_end()
            await self.push_frame(frame, direction)

    return SpeechSink()


class TTSPipeline:
    """A dedicated Pipecat loop that synthesizes one sentence at a time."""

    def __init__(
        self,
        service: "TTSService",
        sink: "FrameProcessor",
        recorder: SpeechRecorder,
        loop: asyncio.AbstractEventLoop,
        thread: threading.Thread,
        worker: "PipelineWorker",
        runner: "asyncio.Task[None]",
    ) -> None:
        self._service = service
        self._sink = sink
        self._recorder = recorder
        self._loop = loop
        self._thread = thread
        # Held for the one-sentence-at-a-time rule.
        self._sentence_lock = threading.Lock()
        # Tracks the sentence currently holding the claim lock.
        self._speaking: SpokenSentence | None = None
        self._claim = threading.Lock()
        self._worker: "PipelineWorker | None" = worker
        self._runner: "asyncio.Task[None] | None" = runner

    @property
    def service(self) -> "TTSService":
        """The service this pipeline speaks through."""
        return self._service

    @classmethod
    def start(cls, service: "TTSService") -> "TTSPipeline":
        """Start a pipeline around an already-built service."""
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_run_loop,
            args=(loop,),
            name=f"{CFG.ROOT_GROUP_NAME}-speech-tts",
            daemon=True,
        )
        thread.start()
        recorder = SpeechRecorder()
        sink = create_speech_sink(recorder)
        try:
            worker, runner = _call(loop, _serve(service, sink, recorder))
        except BaseException:
            # Do not leave a thread or loaded model after startup fails.
            _stop_loop(loop, thread)
            raise
        return cls(service, sink, recorder, loop, thread, worker, runner)

    def speak(
        self, text: str, timeout: float = FIRST_CHUNK_TIMEOUT_SECONDS
    ) -> SpeechAudio:
        """Return *text* as audio, or raise if synthesis fails to start."""
        self._sentence_lock.acquire()
        try:
            sentence = self._recorder.start_sentence()
        except BaseException:
            # No sentence claimed the lock.
            self._sentence_lock.release()
            raise
        with self._claim:
            self._speaking = sentence
        try:
            _call(self._loop, self._say(text))
            first = sentence.wait_for_chunk(timeout)
        except BaseException:
            # Close and interrupt before releasing the claim, so late audio
            # cannot reach the next sentence.
            self._drop(sentence)
            raise
        return SpeechAudio(
            sentence.sample_rate,
            self._read(sentence, first),
            close=lambda: self._drop(sentence),
        )

    async def _say(self, text: str) -> None:
        """Hand the service one sentence to say."""
        # lazy: heavy third-party — pipecat is the `voice` extra.
        from pipecat.frames.frames import TTSSpeakFrame

        worker = self._worker
        if worker is None:
            raise RuntimeError("the Pipecat speech pipeline is not running")
        await worker.queue_frame(TTSSpeakFrame(text))

    def _read(self, sentence: SpokenSentence, first: bytes) -> Iterator[bytes]:
        """Yield *sentence*'s audio until completion or failure."""
        try:
            yield first
            while sentence.is_open:
                item = sentence.take(_SILENCE_TIMEOUT_SECONDS)
                if isinstance(item, _End):
                    if item.problem:
                        logger.warning(f"Speech was cut off: {item.problem}")
                    return
                yield item
        finally:
            self._release(sentence)

    def _drop(self, sentence: SpokenSentence) -> None:
        """Stop reading *sentence* and interrupt its synthesis."""
        sentence.close()
        with self._claim:
            if self._speaking is not sentence:
                return
            self._speaking = None
        try:
            _call(self._loop, self._interrupt(), _TIMEOUT_SECONDS)
        except (RuntimeError, TimeoutError) as exc:
            # Audio is already dropped; only interruption reporting can fail.
            logger.warning(f"Could not stop the Pipecat speech service: {exc}")
        finally:
            # Always release the one-sentence lock after interruption.
            self._sentence_lock.release()

    async def _interrupt(self) -> None:
        """Tell the service to stop saying what it is saying."""
        # lazy: heavy third-party — pipecat is the `voice` extra.
        from pipecat.frames.frames import InterruptionFrame

        worker = self._worker
        if worker is None:
            return
        await worker.queue_frame(InterruptionFrame())

    def _release(self, sentence: SpokenSentence) -> None:
        """Release the speaking claim if it still belongs to *sentence*."""
        with self._claim:
            if self._speaking is not sentence:
                return
            self._speaking = None
        self._sentence_lock.release()

    def close(self) -> None:
        """Stop the worker and loop without raising."""
        worker, self._worker = self._worker, None
        if worker is None:
            return
        try:
            _call(self._loop, self._stop_worker(worker), _TIMEOUT_SECONDS)
        except (RuntimeError, TimeoutError) as exc:
            logger.warning(f"Stopping the Pipecat speech pipeline failed: {exc}")
        finally:
            self._recorder.record_stopped("the Pipecat speech pipeline was closed")
            _stop_loop(self._loop, self._thread)

    async def _stop_worker(self, worker: "PipelineWorker") -> None:
        """Cancel the worker and wait briefly for it to unwind."""
        await close_quietly(worker.cancel, "the Pipecat speech worker")
        runner, self._runner = self._runner, None
        if runner is None:
            return
        done, _ = await asyncio.wait({runner}, timeout=_TIMEOUT_SECONDS)
        if not done:
            done = await cancel_and_wait(
                runner, "The Pipecat speech pipeline", _TIMEOUT_SECONDS
            )
        for task in done:
            if not task.cancelled():
                task.exception()


async def _serve(
    service: "TTSService", sink: "FrameProcessor", recorder: SpeechRecorder
) -> "tuple[PipelineWorker, asyncio.Task[None]]":
    """Build and start the worker on this pipeline's event loop."""
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.utils.asyncio.task_manager import TaskManager
    from pipecat.workers.base_worker import WorkerParams

    def on_service_error(_service: object, error: "ErrorFrame") -> None:
        """Record a service error."""
        recorder.record_failure(error.error)

    def on_worker_stopped(task: "asyncio.Task[None]") -> None:
        """Record worker termination for any waiting sentence."""
        reason = "the Pipecat worker stopped"
        if not task.cancelled() and task.exception() is not None:
            reason = f"{reason}: {task.exception()}"
        recorder.record_stopped(reason)

    service.add_event_handler("on_error", on_service_error)
    worker = PipelineWorker(
        # Keep the worker alive between sentences; teardown owns shutdown.
        Pipeline([service, sink]),
        idle_timeout_secs=None,
    )
    # Bind TaskManager to this pipeline's loop.
    runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
    runner.add_done_callback(on_worker_stopped)
    return worker, runner


def _call(
    loop: asyncio.AbstractEventLoop,
    coroutine: "Coroutine[object, object, _T]",
    timeout: float | None = None,
) -> "_T":
    """Run *coroutine* on *loop* and wait for its result."""
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    try:
        return future.result(timeout)
    except BaseException:
        future.cancel()
        raise


def _stop_loop(loop: asyncio.AbstractEventLoop, thread: threading.Thread) -> None:
    """Stop *loop*, and wait, briefly, for its thread to end."""
    loop.call_soon_threadsafe(loop.stop)
    # `_run_loop` cancels what is left for up to `_TIMEOUT_SECONDS` before it ends.
    thread.join(_TIMEOUT_SECONDS * 2)
    if thread.is_alive():
        logger.warning(
            f"The Pipecat speech loop on {thread.name} did not stop; it is left running"
        )


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Run *loop* on this thread until stopped."""
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
        _cancel_pending(loop)
    finally:
        loop.close()


def _cancel_pending(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel every task still on *loop*, waiting a bounded time for them to end."""
    tasks = asyncio.all_tasks(loop)
    for task in tasks:
        task.cancel()
    if tasks:
        loop.run_until_complete(asyncio.wait(tasks, timeout=_TIMEOUT_SECONDS))
        for task in tasks:
            if task.done() and not task.cancelled():
                task.exception()
    loop.run_until_complete(loop.shutdown_asyncgens())
