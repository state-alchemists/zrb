"""Feeding zrb's captured audio into a Pipecat pipeline.

`listen` keeps the microphone (ADR-0106, principle 1): zrb captures as it does
today and these frames are pushed in from outside, so a second audio client can
never contend for the device.

What lives here is stage 1 of that migration — the input side only. The
dictation and speech paths are untouched and nothing calls into this module yet;
its tests are what prove the transport works.

Pipecat is the `voice` extra and is imported inside each factory rather than at
module level: every module under `src/zrb` has to import on its own
(`test_every_module_imports_with_its_parents_stubbed`), and an install without the
voice extra must not pay for the voice stack. The `TYPE_CHECKING` import is what
lets the signatures name pipecat's real types without that cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.dictation.listen import SAMPLE_RATE

if TYPE_CHECKING:
    from pipecat.frames.frames import Frame, InputAudioRawFrame, StartFrame
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.transports.base_input import BaseInputTransport

__all__ = ["create_audio_counter", "create_input_transport", "push_audio"]


def create_input_transport(sample_rate: int = SAMPLE_RATE) -> BaseInputTransport:
    """A Pipecat input transport that zrb pushes its captured audio into.

    The device is not needed, and PortAudio stays out of the picture: pipecat's
    own `BaseInputTransport.process_frame` feeds an `InputAudioRawFrame` pushed
    in from outside through the same VAD path as audio it captured itself. The
    one gap is `start`, whose base implementation clears its paused flags and
    stops — it never calls `set_transport_ready`, which is the call that creates
    the queue a pushed frame is read from. Without it the pushed audio is never
    drained, so this subclass adds exactly that call (ADR-0106; measured, not
    assumed).
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
    """A pipeline sink that keeps every audio frame handed to it.

    Stage 1's exit criterion is a count — as many blocks have to come out as
    went in — and this is where that count is read from.
    """
    # lazy: heavy third-party — pipecat is the `voice` extra.
    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameProcessor

    class AudioCounter(FrameProcessor):
        """Holds the audio frames it has seen, in arrival order."""

        def __init__(self) -> None:
            super().__init__()
            self.audio_frames: list[InputAudioRawFrame] = []
            self.frame_count = 0

        @property
        def bytes_received(self) -> int:
            """Total audio bytes that reached this sink."""
            return sum(len(frame.audio) for frame in self.audio_frames)

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            self.frame_count += 1
            if isinstance(frame, InputAudioRawFrame):
                self.audio_frames.append(frame)
            await self.push_frame(frame, direction)

    return AudioCounter()
