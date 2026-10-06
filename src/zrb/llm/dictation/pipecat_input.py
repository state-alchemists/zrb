"""Feeding zrb's captured audio into a Pipecat pipeline.

`listen` keeps the microphone: frames are pushed in from outside, so a second
audio client never contends for the device. The pipeline ends at an audio
counter, so nothing downstream of the transport acts on the audio, and turning
it on cannot change what zrb hears or says
(`docs/architecture/3-peripheral-flow/voice-on-pipecat.md`).

`push` only queues a block, so `AudioPipeline.close` catches the far end up
before it stops the worker: the last blocks of a listening are the ones a
teardown would otherwise drop, the trailing silence among them.

Pipecat is the `voice` extra, so it is imported inside each factory; the
`TYPE_CHECKING` import lets signatures name its types without that cost.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.dictation.listen import SAMPLE_RATE
from zrb.llm.dictation.teardown import cancel_and_wait, close_quietly

if TYPE_CHECKING:
    # No `InputAudioRawFrame`: each factory imports it at call time, and naming
    # it here as well makes pyflakes read those imports as redefinitions (F811)
    # and this one as unused (F401).
    from pipecat.frames.frames import Frame, StartFrame
    from pipecat.pipeline.task import PipelineWorker
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.transports.base_input import BaseInputTransport

logger = logging.getLogger(__name__)

__all__ = [
    "AudioPipeline",
    "AudioTally",
    "SpeechMetrics",
    "SpeechMetricsRecorder",
    "create_audio_counter",
    "create_input_transport",
    "create_speech_metrics_stage",
    "create_voice_activity_detector",
    "is_pipecat_available",
    "push_audio",
]

#: How long the transport may take to process its `StartFrame` before the
#: pipeline is given up on, and how long closing it may take to unwind.
_START_TIMEOUT_SECONDS = 10.0
_CLOSE_TIMEOUT_SECONDS = 5.0

#: How long the blocks already handed over may take to reach the far end before
#: a teardown gives up on them, and how often that end is read while it catches
#: up. A block is a few milliseconds of audio, so the wait is short; the timeout
#: is what stops a pipeline that has stopped taking blocks from holding up the
#: listening around it.
_DRAIN_TIMEOUT_SECONDS = 5.0
_DRAIN_POLL_SECONDS = 0.01


def is_pipecat_available() -> bool:
    """Whether the `voice` extra's Pipecat is installed, without importing it.

    An install without the extra must not pay for the voice stack, and the
    capture path asks this before it builds a pipeline.
    """
    return importlib.util.find_spec("pipecat") is not None


def create_input_transport(
    sample_rate: int = SAMPLE_RATE,
    on_ready: Callable[[], None] | None = None,
) -> BaseInputTransport:
    """A Pipecat input transport that zrb pushes its captured audio into.

    The device is not needed, and PortAudio stays out of the picture: pipecat's
    own `BaseInputTransport.process_frame` feeds an `InputAudioRawFrame` pushed
    in from outside through the same VAD path as audio it captured itself. The
    one gap is `start`, whose base implementation never calls
    `set_transport_ready`, the call that creates the queue a pushed frame is
    read from; this subclass adds it. *on_ready* is called once that
    queue exists, since a frame pushed before then has nowhere to go.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra, and this module is
    # reached from the pipeline wiring rather than from startup.
    from pipecat.transports.base_input import BaseInputTransport
    from pipecat.transports.base_transport import TransportParams

    class ZrbInputTransport(BaseInputTransport):
        """`BaseInputTransport` whose `start` also finishes starting up."""

        async def start(self, frame: StartFrame) -> None:
            await super().start(frame)
            await self.set_transport_ready(frame)
            if on_ready is not None:
                on_ready()

    return ZrbInputTransport(
        TransportParams(audio_in_enabled=True, audio_in_sample_rate=sample_rate)
    )


async def push_audio(
    transport: BaseInputTransport, chunk: bytes, sample_rate: int = SAMPLE_RATE
) -> None:
    """Push one block of mono 16-bit PCM into *transport*, at *sample_rate*.

    The frame carries its own sample rate and channel count, so a block goes in
    exactly as `listen` produced it and is analysed at the rate it was captured
    at: `SAMPLE_RATE` is the right label only for a transport started at it, and
    a block labeled otherwise is one the detector reads at the wrong speed. The
    transport has to have started first: until its `StartFrame` is processed
    there is no queue to put a block on.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameDirection

    await transport.process_frame(
        InputAudioRawFrame(audio=chunk, sample_rate=sample_rate, num_channels=1),
        FrameDirection.DOWNSTREAM,
    )


@dataclass
class AudioTally:
    """What the pipeline's far end has been handed, counted as it arrives.

    Plain Python, so it is testable without a pipeline and readable from outside
    the sink that writes it: *frame_count* is every frame that reached the sink,
    *bytes_received* the audio among them. `AudioPipeline.close` reads the byte
    count to tell whether the blocks it pushed have arrived, which is the one
    thing a stage that decides nothing is there to prove.
    """

    frame_count: int = 0
    bytes_received: int = 0


def create_audio_counter(tally: AudioTally) -> FrameProcessor:
    """A pipeline sink that counts the frames and audio handed to *tally*.

    Nothing is kept: a hands-free session runs for hours, and the count is all
    this end is read for.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class AudioCounter(FrameProcessor):
        """Counts the frames it has seen, and the audio bytes among them."""

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            tally.frame_count += 1
            if isinstance(frame, InputAudioRawFrame):
                tally.bytes_received += len(frame.audio)
            await self.push_frame(frame, direction)

    return AudioCounter()


@dataclass(frozen=True)
class SpeechMetrics:
    """What the pipeline's voice-activity detector reported about speech.

    *speech_segments* is how many speech segments began; *speech_seconds* how
    long the ones that also ended lasted, measured from the audio rather than
    from the clock. A segment still open when this is read has no end yet, so its
    time is not in the total.
    """

    speech_segments: int
    speech_seconds: float

    def summary(self) -> str:
        """One line saying what the pipeline heard while it was fed."""
        return (
            f"{self.speech_segments} speech segment(s), "
            f"{self.speech_seconds:.1f}s of speech"
        )


class SpeechMetricsRecorder:
    """Accumulates what the pipeline reports about speech, and nothing else.

    The accounting is plain Python, so it is testable without a pipeline and
    without audio: the stage built by `create_speech_metrics_stage` classifies
    the frames, hands each block of sound over with `record_audio`, and calls
    `record_speech_started`/`record_speech_stopped`. The verb is *record* rather
    than one of ADR-0098's, because the method adds an observation to a running
    total instead of handling an event or returning a value.

    What is measured is the audio, not the clock. The detector's frames arrive
    while the pipeline works through what was pushed into it, so the interval
    between two of them as the processor sees them is the pipeline's own
    latency: capture pushed as a burst is worked through in milliseconds, and a
    busy pipeline takes longer over the same speech than the user did. The
    length the audio frames carry is the length the user spoke, however fast
    they were worked through.
    """

    def __init__(self) -> None:
        self._speech_segments = 0
        self._speech_seconds = 0.0
        self._open_seconds = 0.0
        self._is_speaking = False

    def record_speech_started(self) -> None:
        """Speech began. Counted even if it never ends; a second start leaves
        the audio already measured for the segment being timed where it is."""
        self._speech_segments += 1
        self._is_speaking = True

    def record_audio(self, seconds: float) -> None:
        """Add the length of one block of audio, while speech is being heard.

        Audio that arrives with no segment open is audio the detector has not
        called speech, and is not timed."""
        if self._is_speaking:
            self._open_seconds += seconds

    def record_speech_stopped(self) -> None:
        """Speech ended: add the audio measured for the segment. A stop with no
        start heard is not speech this pipeline saw begin, and adds nothing."""
        if not self._is_speaking:
            return
        self._speech_seconds += self._open_seconds
        self._open_seconds = 0.0
        self._is_speaking = False

    def get_metrics(self) -> SpeechMetrics:
        """What has been recorded so far."""
        return SpeechMetrics(self._speech_segments, self._speech_seconds)


def create_voice_activity_detector() -> FrameProcessor:
    """A pipeline stage running Pipecat's voice-activity detection.

    Without it the pipeline carries bytes and nothing else: the detector is
    what tells speech from silence, and what the metrics stage counts. It
    decides nothing — zrb's own cutting still decides where an utterance
    begins and ends — so it cannot change what zrb hears or says. The model
    ships inside Pipecat and runs offline; it is loaded when the pipeline
    starts, which is why this is reached only with the flag on.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.processors.audio.vad_processor import VADProcessor

    return VADProcessor(vad_analyzer=SileroVADAnalyzer())


def create_speech_metrics_stage(recorder: SpeechMetricsRecorder) -> FrameProcessor:
    """A pipeline stage that times the speech the detector reports.

    It decides nothing: the segments and the audio it sees are handed to
    *recorder*, and every frame goes on downstream unchanged. The frames are
    Pipecat's own — `InputAudioRawFrame` carries the sound and
    `VADUserStartedSpeakingFrame`/`VADUserStoppedSpeakingFrame` the detector's
    verdict — so this reads the detector rather than analysing audio a second
    time, and takes its length from the frame's own sample count and rate rather
    than from the clock it happens to run on (`SpeechMetricsRecorder`).
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import (
        InputAudioRawFrame,
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )
    from pipecat.processors.frame_processor import FrameProcessor

    class SpeechMetricsStage(FrameProcessor):
        """Times the speech the detector reports; forwards every frame."""

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            # A frame with no rate has no length to take: the transport would
            # not have started on one, so this is a pipeline already wrong.
            if isinstance(frame, InputAudioRawFrame) and frame.sample_rate > 0:
                recorder.record_audio(frame.num_frames / frame.sample_rate)
            elif isinstance(frame, VADUserStartedSpeakingFrame):
                recorder.record_speech_started()
            elif isinstance(frame, VADUserStoppedSpeakingFrame):
                recorder.record_speech_stopped()
            await self.push_frame(frame, direction)

    return SpeechMetricsStage()


@dataclass
class AudioPipeline:
    """A running Pipecat pipeline that zrb's captured blocks are pushed into.

    It ends at *counter*, an `AudioCounter` writing *tally*, so nothing
    downstream of the transport acts on the audio; the speech-activity detector
    and the metrics stage in front of it observe the audio without deciding
    anything about it. *pushed_bytes* is what `push` has handed over, which
    *tally* is read against to know that a listening's last block has arrived
    rather than being cut off by the teardown.
    """

    worker: "PipelineWorker"
    runner: "asyncio.Task[None]"
    transport: "BaseInputTransport"
    counter: "FrameProcessor"
    tally: AudioTally
    recorder: SpeechMetricsRecorder
    sample_rate: int = SAMPLE_RATE
    pushed_bytes: int = 0

    @classmethod
    async def start(cls, sample_rate: int = SAMPLE_RATE) -> "AudioPipeline":
        """Start the pipeline on the running loop, ready for `push`.

        A worker does not start itself — `run` is the coroutine that drives it —
        so this pipeline owns that task, and `close` ends both. `TaskManager`
        binds to the caller's running loop.
        """
        # lazy: heavy third-party — pipecat is the `voice` extra.
        from pipecat.frames.frames import StartFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineWorker
        from pipecat.pipeline.worker import PipelineParams
        from pipecat.utils.asyncio.task_manager import TaskManager
        from pipecat.workers.base_worker import WorkerParams

        ready = asyncio.Event()
        transport = create_input_transport(sample_rate, ready.set)
        recorder = SpeechMetricsRecorder()
        tally = AudioTally()
        counter = create_audio_counter(tally)
        worker = PipelineWorker(
            Pipeline(
                [
                    transport,
                    create_voice_activity_detector(),
                    create_speech_metrics_stage(recorder),
                    counter,
                ]
            ),
            # The detector analyses at the transport's own rate, which reaches
            # it through the worker's params and not through the transport's.
            params=PipelineParams(audio_in_sample_rate=sample_rate),
        )
        runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
        pipeline = cls(worker, runner, transport, counter, tally, recorder, sample_rate)
        ready_waiter = asyncio.create_task(ready.wait())
        try:
            await worker.queue_frames([StartFrame()])
            # `queue_frames` only queues the frame: until the transport has
            # processed it there is no queue for a pushed block.
            done, _ = await asyncio.wait(
                {ready_waiter, runner},
                timeout=_START_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                raise TimeoutError
            if runner in done:
                # The worker is gone for good: `await runner` raises when it
                # failed, and a clean exit with the transport still unready
                # means readiness can never come, so waiting on it would hang
                # where the old timeout used to give up.
                await runner
                raise RuntimeError(
                    "The Pipecat worker exited before the transport was ready"
                )
            await ready_waiter
        except BaseException:
            # A pipeline that did not come up must not leave its worker running.
            await pipeline.close()
            raise
        finally:
            if not ready_waiter.done():
                ready_waiter.cancel()
                await asyncio.gather(ready_waiter, return_exceptions=True)
        return pipeline

    async def push(self, chunk: bytes) -> None:
        """Hand one captured block over, as `push_audio` takes it.

        Only queued: the transport takes it from there, so what was handed over
        is counted here and read against the far end by `close`.
        """
        self.pushed_bytes += len(chunk)
        await push_audio(self.transport, chunk, self.sample_rate)

    def get_speech_metrics(self) -> SpeechMetrics:
        """What the pipeline heard while it was fed: the speech segments its
        detector reported, and how long they lasted."""
        return self.recorder.get_metrics()

    async def close(self) -> None:
        """Stop the pipeline and wait, briefly, for its task to unwind.

        The blocks already handed over are drained first, so the worker is not
        stopped while one of them is still on its way: `push` only queues a
        block, and a teardown that stops first drops whatever is queued — the
        trailing silence included, which is the silence the detector needs to
        report the end of the segment it closes, and the count this stage is
        measured on comes up short. Draining is bounded, so a pipeline that has
        stopped taking blocks is given up on rather than waited on.

        Never raises: this runs in the listening's `finally`, where an escaping
        failure would end hands-free for the session. A runner still going after
        the wait is cancelled; one that swallows that is logged and left.
        `asyncio.wait`, not `wait_for`, so the worker's own failure is not raised
        a second time here — whoever pushed its last frame has already seen it —
        and its exception is read off below so the loop does not log it as
        never retrieved.
        """
        await self._drain()
        await close_quietly(self.worker.cancel, "the Pipecat worker")
        done, _ = await asyncio.wait({self.runner}, timeout=_CLOSE_TIMEOUT_SECONDS)
        if not done:
            done = await cancel_and_wait(
                self.runner, "The Pipecat pipeline", _CLOSE_TIMEOUT_SECONDS
            )
        for task in done:
            if not task.cancelled():
                task.exception()

    async def _drain(self) -> None:
        """Wait, at most `_DRAIN_TIMEOUT_SECONDS`, for the blocks handed over to
        arrive at the far end.

        The far end's byte count is the whole of what this stage is turned on to
        prove — a block that never arrives is a block the detector never heard —
        so a teardown reads it rather than trusting that a queued block was
        taken. A runner that is already done can deliver nothing, so the wait
        ends with it instead of standing the whole timeout; a pipeline that is
        still up and still empty-handed is given up on at the deadline, and what
        did not arrive is named, once, rather than raising.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _DRAIN_TIMEOUT_SECONDS
        while (
            self.tally.bytes_received < self.pushed_bytes
            and not self.runner.done()
            and loop.time() < deadline
        ):
            await asyncio.sleep(_DRAIN_POLL_SECONDS)
        missing = self.pushed_bytes - self.tally.bytes_received
        if missing > 0:
            logger.warning(
                f"{missing} byte(s) of captured audio never reached the Pipecat "
                "pipeline and were not analysed"
            )
