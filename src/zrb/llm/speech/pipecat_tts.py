"""Saying zrb's sentences through a Pipecat text-to-speech service.

Stage 3 of the voice migration: the synthesis half. Pipecat makes the audio; zrb
still decides when it is heard — which sentence, in which order, and whether it
is held or dropped when the user talks over it. Playback stays zrb's, which is
what lets dictation cancel zrb's own voice out of the microphone and pause it
mid-sentence, and what makes a sentence that was cut off stay cut off
(ADR-0103).

One sentence crosses at a time. zrb hands the pipeline a `TTSSpeakFrame` and
reads the `TTSAudioRawFrame`s it answers with; the service says when that
sentence is over itself. Every service zrb registers asks Pipecat for that
(`push_start_frame=True, push_stop_frames=True`), so a speak frame is answered
with a `TTSStartedFrame`, its audio, and a `TTSStoppedFrame` — nothing here
guesses at a boundary, or waits out a timeout for one.

Three threads meet here, which is why every crossing is a queue or a lock and
never a shared attribute: the speaker's thread calls `create_audio` and blocks
until the first chunk exists, the pipeline's own loop thread runs the service,
and the player's thread reads the chunks out as it plays them. A sentence nobody
plays is dropped on both sides — `close` ends the read, and an
`InterruptionFrame` ends the synthesis.
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

#: How long a sentence may take to start being heard before it is given up on. A
#: local model still loading its weights, or fetching them the first time, is the
#: case this bounds.
FIRST_CHUNK_TIMEOUT_SECONDS = 30.0

#: How long the pipeline may take to unwind, or the service to be told to stop,
#: once it has been asked to.
_TIMEOUT_SECONDS = 5.0

#: How long a sentence may be silent before the read gives up on it. Not a
#: boundary — a boundary is the service's own `TTSStoppedFrame`. This is the
#: service that is running but has stopped saying anything, so that whoever is
#: playing the sentence is not left reading it forever.
_SILENCE_TIMEOUT_SECONDS = 60.0

_T = TypeVar("_T")


class _End:
    """The end of one sentence's audio, and why it ended.

    *problem* is what went wrong, or ``None`` when the service said the sentence
    was over. It travels the same queue as the audio, so it cannot arrive before
    the audio it ends.
    """

    def __init__(self, problem: str | None = None) -> None:
        self.problem = problem


class SpokenSentence:
    """One sentence's audio as the service makes it, and who is reading it.

    Created by `SpeechRecorder.start_sentence`, which makes it the sentence the
    pipeline's sink writes to; dropping it is what `SpeechAudio.close` does, so
    audio arriving late for a sentence nobody wants cannot be taken for the
    sentence that replaced it.

    Written on the pipeline's loop and read on the thread playing the audio, so
    every crossing is the queue, never a shared attribute.

    Two ways to end, and they differ in what they do to the audio still queued:
    the service saying the sentence is over leaves it to be read to its end, and
    a sentence being dropped stops the read where it stands.
    """

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
        """This sentence's first chunk of audio, or a raise saying why not.

        A raise, not an empty chunk: a service that cannot say this sentence is
        worth a local voice saying it instead, and a caller cannot tell silence
        from a failure by listening to it.
        """
        item = self._take(timeout)
        if isinstance(item, _End):
            raise RuntimeError(item.problem or "the Pipecat service said nothing")
        return item

    def take(self, timeout: float) -> "bytes | _End":
        """What the service produced next: a chunk, or the end of the sentence.

        Silence is the end of the sentence as far as a reader is concerned, but it
        is named as the silence it is rather than as the service finishing.
        """
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
    """Which sentence the pipeline's sink is writing to.

    A sink is built once, when the pipeline starts, and is handed one sentence at
    a time from another thread, so this is what says whose answers the frames
    arriving now are. It also remembers a pipeline that stopped, which is what
    turns a session's next sentence into a failure that gets reported rather than
    a wait for a frame nobody can carry.
    """

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
    """A pipeline sink that hands every chunk of speech to *recorder*.

    It reads Pipecat's frames and decides nothing: audio is audio, and the
    service's own `TTSStoppedFrame` is what says a sentence ended. Whether a
    sentence should be heard at all is the speaker's question, asked of zrb's own
    playback policy rather than of the pipeline.

    A failure is deliberately not read here. A service that fails reports it
    through `push_error`, which travels *upstream*, and a sink at the far end of
    the pipeline is the one place that will never see it; the service's own
    `on_error` is where that is caught (`_serve`).
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStoppedFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class SpeechSink(FrameProcessor):
        """Records the service's audio, and decides nothing about it."""

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, TTSAudioRawFrame):
                recorder.record_audio(frame.audio, frame.sample_rate)
            elif isinstance(frame, TTSStoppedFrame):
                recorder.record_end()
            await self.push_frame(frame, direction)

    return SpeechSink()


class TTSPipeline:
    """A running Pipecat pipeline whose service says what zrb hands it.

    Built once per backend and kept, because the expensive part is the model a
    service loads in its constructor: one built per sentence would pay for the
    model per sentence. One sentence is synthesized at a time — one service is one
    voice, and two sentences' audio arriving together could not be told apart.

    It owns a loop of its own, on a thread of its own, because the seam zrb plays
    through is synchronous — `create_audio` is called on the speaker's thread and
    returns audio for the player to read as it plays it — while Pipecat's is not.
    """

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
        # Held from the moment a sentence is asked for until its audio has all
        # been read, or dropped: the one-sentence-at-a-time rule.
        self._sentence_lock = threading.Lock()
        # The claim the lock stands for: which sentence is being spoken now, and
        # the lock guarding it. A sentence ending and the next one starting is done
        # by whichever of the two comes first, from whichever thread it comes on.
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
        """Start a pipeline around *service*, ready to be handed a sentence.

        The service arrives already built, because building it is the caller's
        once-only cost: a manager's `create_service` is what loads the model, and
        this is where the result is put to work. A worker does not start itself —
        `run` is the coroutine that drives it — so the pipeline owns that task.
        """
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
            # Half a pipeline is worse than none: a caller that cannot be given one
            # must not be left with a thread and a loaded model running.
            _stop_loop(loop, thread)
            raise
        return cls(service, sink, recorder, loop, thread, worker, runner)

    def speak(
        self, text: str, timeout: float = FIRST_CHUNK_TIMEOUT_SECONDS
    ) -> SpeechAudio:
        """*text* as audio zrb plays, or a raise when the service cannot say it.

        Blocks until the first chunk exists. Two things come out of that wait: the
        rate the audio is really at, rather than zrb's guess at it, and a failure
        where the speaker still has a local voice to fall back on — rather than
        half way through playing the sentence.
        """
        self._sentence_lock.acquire()
        try:
            sentence = self._recorder.start_sentence()
        except BaseException:
            # Nothing was asked for, so no claim was taken: the lock is the only
            # thing to give back.
            self._sentence_lock.release()
            raise
        with self._claim:
            self._speaking = sentence
        try:
            _call(self._loop, self._say(text))
            first = sentence.wait_for_chunk(timeout)
        except BaseException:
            # Not `_release`: the service may still be making this sentence, and
            # the sentence after it would be handed whatever arrives late for
            # this one, because `start_sentence` moves the sink onto it. Dropping
            # is what closes the sentence and tells the service to stop before
            # the claim is given up — the same cleanup a sentence already being
            # read gets — so the next one is asked of a service that has been
            # told, and nothing can still be fed into it.
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
        """*sentence*'s audio, *first* included, until the service says it is over.

        A failure after the audio started ends the read rather than raising: the
        sentence was heard as far as it came, which is what a stream that stops
        part-way sounds like, and the warning names what went wrong.
        """
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
        """Stop reading *sentence*, and stop the service making it.

        What `SpeechAudio.close` calls, from whichever thread drops the audio — the
        player's, when the user talks over zrb. The `InterruptionFrame` is what
        tells the service to stop: Pipecat ends that sentence's audio context and
        its synthesis task there, so audio nobody will hear is not synthesized to
        its end.

        The sentence is dropped before the service is interrupted, and the claim is
        given up only after the frame is queued: released any earlier, the sentence
        after this one could be asked for first, and the interruption would land on
        it. A sentence whose audio was all read has already given up its claim, so
        this finds nothing to interrupt.
        """
        sentence.close()
        with self._claim:
            if self._speaking is not sentence:
                return
            self._speaking = None
        try:
            _call(self._loop, self._interrupt(), _TIMEOUT_SECONDS)
        except (RuntimeError, TimeoutError) as exc:
            # The audio is dropped either way, which is what the caller asked for:
            # this is only about whether the service can be told to stop.
            logger.warning(f"Could not stop the Pipecat speech service: {exc}")
        finally:
            # Given back whatever happened above. The lock is the one-sentence rule,
            # so a sentence dropped while it stayed held would have every later
            # `speak` waiting for a sentence that is already over. `finally` and not
            # the end of the handler, because a failure outside the two types named
            # there, a future the loop cancelled included, leaves just as readily.
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
        """Give up this pipeline's claim on speaking, if it is still this sentence's.

        Called when a sentence's audio has all been read: whichever of that and
        `_drop` comes first lets the next sentence start, and every later one
        finds nothing of its own to give up.
        """
        with self._claim:
            if self._speaking is not sentence:
                return
            self._speaking = None
        self._sentence_lock.release()

    def close(self) -> None:
        """Stop the pipeline and its loop, and let the service's model go.

        Never raises: this runs where a session is being torn down, and a pipeline
        that will not stop must not be what keeps the session from ending. The
        thread is stopped whatever the worker did.
        """
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
        """Cancel the worker and wait, briefly, for it to unwind.

        A worker still going after the wait is cancelled; one that swallows that is
        logged and left. `asyncio.wait`, not `wait_for`, so a worker that had
        already failed is not raised a second time here — whoever pushed its last
        frame has seen it — and its exception is read off so the loop does not log
        it as never retrieved.
        """
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
    """Build the worker, and start it, on the loop this runs on.

    Built here rather than by a running pipeline, so that nothing is ever half
    made: the object zrb holds is one whose worker is already going.

    The two callbacks are what turn a pipeline's own failures into answers for
    whoever is waiting. A synthesis that raises is caught by the service itself,
    which pushes the failure *upstream* and leaves the pipeline running — so the
    sink downstream never sees it, and without the first callback the sentence it
    belonged to would wait out the whole first-chunk timeout to learn nothing is
    coming. Every frame travels through the worker, so once the worker has stopped
    no audio can arrive at all, which is the second.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.utils.asyncio.task_manager import TaskManager
    from pipecat.workers.base_worker import WorkerParams

    def on_service_error(_service: object, error: "ErrorFrame") -> None:
        """Report a failure the service pushed.

        Every event handler takes the object that raised it first, which is the
        service here, and this one has no use for it
        (`pipecat.utils.base_object.BaseObject._run_handler`).
        """
        recorder.record_failure(error.error)

    def on_worker_stopped(task: "asyncio.Task[None]") -> None:
        """Report the worker stopping, so a sentence waiting on it is not left waiting.

        A done callback rather than a task watching the worker: the failure is read
        off the task as it ends, which is also what stops the loop from reporting it
        later as never retrieved.
        """
        reason = "the Pipecat worker stopped"
        if not task.cancelled() and task.exception() is not None:
            reason = f"{reason}: {task.exception()}"
        recorder.record_stopped(reason)

    service.add_event_handler("on_error", on_service_error)
    worker = PipelineWorker(
        # Idle is this pipeline's normal state, not a fault: zrb keeps it for
        # the session and hands it sentences one at a time, so it sits with no
        # frames between them and Pipecat's watchdog would take it away for that
        # (`idle_timeout_secs` defaults to 300s, armed by the last
        # `BotSpeakingFrame`, after which every later sentence fails with "the
        # Pipecat worker stopped"). `None` leaves the monitor off; the speaker
        # closes this pipeline from its own teardown.
        Pipeline([service, sink]),
        idle_timeout_secs=None,
    )
    # Pipecat's `TaskManager` binds to the loop it is created on, which is this
    # pipeline's, so no second loop is created for a service started here.
    runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
    runner.add_done_callback(on_worker_stopped)
    return worker, runner


def _call(
    loop: asyncio.AbstractEventLoop,
    coroutine: "Coroutine[object, object, _T]",
    timeout: float | None = None,
) -> "_T":
    """Run *coroutine* on *loop*, and wait for its answer.

    A future that never answers is cancelled rather than left to run unwatched.
    """
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
    """Run *loop* on this thread until it is told to stop.

    A daemon thread's, because a session that ends without closing its backend
    must not hold the process open for a loop nobody will ask anything else of.
    """
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
