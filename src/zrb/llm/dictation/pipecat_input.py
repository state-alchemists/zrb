"""Feeding zrb's captured audio into a Pipecat pipeline.

`listen` keeps the microphone (ADR-0107, principle 1): zrb captures as it does
today and these frames are pushed in from outside, so a second audio client can
never contend for the device.

Stage 1 of that migration is what lives here, and it is the input side only: the
pipeline ends at an audio counter, so nothing downstream of the transport acts
on the audio and turning it on cannot change what zrb hears or says. It proves
the transport carries zrb's own blocks beside the hand-rolled path that still
decides everything (`docs/architecture/3-peripheral-flow/voice-on-pipecat.md`).

Pipecat is the `voice` extra and is imported inside each factory rather than at
module level: every module under `src/zrb` has to import on its own
(`test_every_module_imports_with_its_parents_stubbed`), and an install without the
voice extra must not pay for the voice stack. The `TYPE_CHECKING` import is what
lets the signatures name pipecat's real types without that cost.
"""

from __future__ import annotations

import asyncio
import importlib.util
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

__all__ = [
    "AudioPipeline",
    "create_audio_counter",
    "create_input_transport",
    "is_pipecat_available",
    "push_audio",
]

#: How long the transport may take to process its `StartFrame` before the
#: pipeline is given up on, and how long closing it may take to unwind.
_START_TIMEOUT_SECONDS = 10.0
_CLOSE_TIMEOUT_SECONDS = 5.0


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
    one gap is `start`, whose base implementation clears its paused flags and
    stops — it never calls `set_transport_ready`, which is the call that creates
    the queue a pushed frame is read from. Without it the pushed audio is never
    drained, so this subclass adds exactly that call (ADR-0107; measured, not
    assumed). *on_ready* is called once that queue exists, since a frame pushed
    before then has nowhere to go.
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


async def push_audio(transport: BaseInputTransport, chunk: bytes) -> None:
    """Push one block of 16 kHz mono 16-bit PCM into *transport*.

    The frame carries its own sample rate and channel count, so a block goes in
    exactly as `listen` produced it. The transport has to have started first:
    until its `StartFrame` is processed there is no queue to put a block on.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameDirection

    await transport.process_frame(
        InputAudioRawFrame(audio=chunk, sample_rate=SAMPLE_RATE, num_channels=1),
        FrameDirection.DOWNSTREAM,
    )


def create_audio_counter() -> FrameProcessor:
    """A pipeline sink that counts the frames and audio handed to it.

    Stage 1's exit criterion is a count — as many blocks have to come out as
    went in — and this is where that count is read from: `frame_count` is every
    frame that reached the sink, `bytes_received` the audio among them. Nothing
    is held: a hands-free session runs for hours, so a sink that kept the frames
    would grow without bound and take the process with it (PR #561 review).
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class AudioCounter(FrameProcessor):
        """Counts the frames it has seen, and the audio bytes among them."""

        def __init__(self) -> None:
            super().__init__()
            self.frame_count = 0
            self.bytes_received = 0

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            self.frame_count += 1
            if isinstance(frame, InputAudioRawFrame):
                self.bytes_received += len(frame.audio)
            await self.push_frame(frame, direction)

    return AudioCounter()


@dataclass
class AudioPipeline:
    """A running Pipecat pipeline that zrb's captured blocks are pushed into.

    Stage 1 of the migration (ADR-0107). It ends at an `AudioCounter`, so nothing
    downstream of the transport acts on the audio and what zrb hears and says is
    still decided by the hand-rolled path; what it proves is that the transport
    carries zrb's own blocks, in order and intact, which is what the turn
    detection of stage 2 is built on. *counter* is that sink: `frame_count` is
    every frame that came out, `bytes_received` how much of it was audio.
    """

    worker: "PipelineWorker"
    runner: "asyncio.Task[None]"
    transport: "BaseInputTransport"
    counter: "FrameProcessor"

    @classmethod
    async def start(cls, sample_rate: int = SAMPLE_RATE) -> "AudioPipeline":
        """Start the pipeline on the running loop, ready for `push`.

        A worker does not start itself — `run` is the coroutine that drives it —
        so its session owns that task, and `close` is what ends both. The device
        is never opened, so `TaskManager` binds to the loop the caller already
        runs in rather than to a second one (ADR-0107; measured, not assumed).
        """
        # lazy: heavy third-party — pipecat is the `voice` extra.
        from pipecat.frames.frames import StartFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineWorker
        from pipecat.utils.asyncio.task_manager import TaskManager
        from pipecat.workers.base_worker import WorkerParams

        ready = asyncio.Event()
        transport = create_input_transport(sample_rate, ready.set)
        counter = create_audio_counter()
        worker = PipelineWorker(Pipeline([transport, counter]))
        runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
        pipeline = cls(worker, runner, transport, counter)
        try:
            await worker.queue_frames([StartFrame()])
            # `queue_frames` only queues the frame: until the transport has
            # processed it there is no queue for a pushed block, and the push
            # fails, so a frame queued but never processed is a start that never
            # finished.
            await asyncio.wait_for(ready.wait(), timeout=_START_TIMEOUT_SECONDS)
        except BaseException:
            # A pipeline that did not come up must not leave its worker running
            # for the life of the event loop. A cancellation is stopped the same
            # way, and re-raised either way.
            await pipeline.close()
            raise
        return pipeline

    async def push(self, chunk: bytes) -> None:
        """Hand one captured block over, as `push_audio` takes it."""
        await push_audio(self.transport, chunk)

    async def close(self) -> None:
        """Stop the pipeline and wait, briefly, for its task to unwind.

        Never raises, and does not leave the task running where it can end it
        (PR #561 review). The ask travels over the worker's own bus, and a
        pipeline already in trouble can fail it: the failure is contained, and a
        task still going after the wait below is cancelled outright — this runs
        in the listening's `finally`, where an escaping failure would end
        hands-free for the session, and a task left behind would outlive the
        microphone it was fed from. A runner that will not stop even then cannot
        be ended from here, only named: the deadline holds, and the log says what
        was left behind. `asyncio.wait`, not `wait_for`, so the
        worker's own failure is not reported a second time here — whoever pushed
        its last frame has already seen it — and its exception is read off below
        so the loop does not later log it as one nobody retrieved.
        """
        await close_quietly(self.worker.cancel, "the Pipecat worker")
        done, _ = await asyncio.wait({self.runner}, timeout=_CLOSE_TIMEOUT_SECONDS)
        if not done:
            done = await cancel_and_wait(
                self.runner, "The Pipecat pipeline", _CLOSE_TIMEOUT_SECONDS
            )
        for task in done:
            if not task.cancelled():
                task.exception()
