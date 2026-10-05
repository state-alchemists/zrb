"""Feeding zrb's captured audio into a Pipecat pipeline.

`listen` keeps the microphone: frames are pushed in from outside, so a second
audio client never contends for the device. The pipeline ends at an audio
counter, so nothing downstream of the transport acts on the audio, and turning
it on cannot change what zrb hears or says
(`docs/architecture/3-peripheral-flow/voice-on-pipecat.md`).

Pipecat is the `voice` extra, so it is imported inside each factory; the
`TYPE_CHECKING` import lets signatures name its types without that cost.
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

    `frame_count` is every frame that reached the sink, `bytes_received` the
    audio among them. Frames are not kept: a hands-free session runs for hours.
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

    It ends at *counter*, an `AudioCounter`, so nothing downstream of the
    transport acts on the audio.
    """

    worker: "PipelineWorker"
    runner: "asyncio.Task[None]"
    transport: "BaseInputTransport"
    counter: "FrameProcessor"

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
        from pipecat.utils.asyncio.task_manager import TaskManager
        from pipecat.workers.base_worker import WorkerParams

        ready = asyncio.Event()
        transport = create_input_transport(sample_rate, ready.set)
        counter = create_audio_counter()
        worker = PipelineWorker(Pipeline([transport, counter]))
        runner = asyncio.create_task(worker.run(WorkerParams(TaskManager())))
        pipeline = cls(worker, runner, transport, counter)
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
        """Hand one captured block over, as `push_audio` takes it."""
        await push_audio(self.transport, chunk)

    async def close(self) -> None:
        """Stop the pipeline and wait, briefly, for its task to unwind.

        Never raises: this runs in the listening's `finally`, where an escaping
        failure would end hands-free for the session. A runner still going after
        the wait is cancelled; one that swallows that is logged and left.
        `asyncio.wait`, not `wait_for`, so the worker's own failure is not raised
        a second time here — whoever pushed its last frame has already seen it —
        and its exception is read off below so the loop does not log it as
        never retrieved.
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
