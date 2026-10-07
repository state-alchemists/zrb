"""Dictation transcribed by a Pipecat speech-to-text service.

The service is the one `zrb.llm.voice` builds from the name the config gives
(`ZRB_LLM_DICTATION_BACKEND`) — `whisper`, `moonshine`, `funasr`, or a service a
project registered in `zrb_init.py` — so what dictation listens through is a
setting, and the models are Pipecat's rather than zrb's.

What crosses back is text, and only text. `AnyDictationBackend` is the seam that
keeps the session ignorant of where the words came from, so the guards that read
a transcript — wake words, stop words, approvals, minimum words, a transcriber's
guess — are untouched and cannot tell a Pipecat service from vosk. That is the
point of the seam: swapping the service must not change what a user's words
mean.

The pipeline is built once per backend and kept, because the expensive part is
the service's own model: Whisper and Moonshine both load it inside the
constructor, so rebuilding one per utterance would pay for the model per
utterance.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.pipecat_stt import STTPipeline
from zrb.llm.voice.manager import stt_manager

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import NoReturn

    from pipecat.services.stt_service import STTService

    from zrb.llm.dictation.config import DictationConfig


class PipecatDictationBackend(AnyDictationBackend):
    """A dictation backend whose transcription is a Pipecat STT service.

    It transcribes a finished utterance, which is the shape zrb already has:
    `listen` cuts the utterance, and this answers with what was said in it. The
    speech-to-text services zrb registers are all segmented that way, so none of
    them streams partials — see `create_stream`, which is `None` for this reason.
    """

    def __init__(self, service_name: str, config: "DictationConfig") -> None:
        self._service_name = service_name
        self._config = config
        self._pipeline: STTPipeline | None = None
        # The loop the pipeline runs on, and the worker task inside it belongs to.
        # The session that closes this backend is synchronous, so it may not be
        # this one, and a pipeline can only be stopped from the loop that owns it.
        self._loop: asyncio.AbstractEventLoop | None = None
        # Set once this backend has let its pipeline go: a `transcribe` arriving
        # after that — a recording the session ended in the middle of — would
        # otherwise build a second service and a second pipeline for a session that
        # is over, and leave both running.
        self._is_closed = False
        # `prepare` is called again for every recording, not only the first, so
        # the look-then-build has to be one step: two callers that both found no
        # pipeline would build two models.
        self._preparing = asyncio.Lock()
        # A teardown runs on a thread of its own when there is no loop to hand the
        # close to, so it can land while a model is loading. Settling the flag and
        # adopting the pipeline together is what decides who lets the pipeline go:
        # the teardown, which finds one, or `prepare`, which finds the flag.
        self._handoff = threading.Lock()

    @property
    def name(self) -> str:
        """How the backend is called in messages."""
        return f"Pipecat ({self._service_name})"

    @property
    def owner_loop(self) -> asyncio.AbstractEventLoop | None:
        """The loop the pipeline runs on, or ``None`` before there is one."""
        return self._loop

    async def prepare(self, report: "Callable[[str], None]") -> None:
        """Load the service and start its pipeline, at most once.

        `report` hears about it first: a model is downloaded or read from disk
        here, which on a first run is the longest wait in the session.

        A pipeline that has stopped counts as no pipeline, and is not one to hand
        a segment to either. It is stopped whether zrb retired it — `transcribe`
        does that for a segment that timed out while still in the service's hands,
        whose answer would be taken for the next segment's — or Pipecat ended its
        worker without `close`. A session that is still listening gets a new one,
        and pays for the model again — the price of a service that had stopped
        answering.
        """
        async with self._preparing:
            if self._is_closed:
                self._refuse_a_closed_service()
            pipeline = self._pipeline
            if pipeline is not None and not pipeline.is_closed:
                return
            if pipeline is not None:
                # A retired pipeline is stopped, and it stopped with a segment it
                # could no longer account for; one whose worker went down holds
                # nothing a segment could reach. Letting go of it here is what
                # lets the next segment start the one it is answered through.
                with self._handoff:
                    self._pipeline, self._loop = None, None
            report(f"Loading the {self._service_name} speech service…")
            service = await asyncio.to_thread(self._create_service)
            loop = asyncio.get_running_loop()
            pipeline = await STTPipeline.start(service)
            with self._handoff:
                abandoned = pipeline if self._is_closed else None
                if abandoned is None:
                    self._loop, self._pipeline = loop, pipeline
            if abandoned is not None:
                # The session ended while its model was loading, and the teardown
                # found no pipeline to close: this is the one it would have closed.
                await abandoned.close()
                self._refuse_a_closed_service()

    def _refuse_a_closed_service(self) -> "NoReturn":
        """Refuse a service for a session that has already let this backend go."""
        raise RuntimeError(
            f"the {self._service_name} speech service was let go, and is "
            "not started again for a session that is over"
        )

    def _create_service(self) -> "STTService":
        """The service this backend is named after.

        Called off the event loop, which is why it is a method of its own: a
        service loads its model in its constructor, and a download or a large
        model must not be seconds the chat spends frozen. Pipecat's processors
        keep no loop-bound state until a worker sets them up, which is what makes
        building one off the loop safe.
        """
        return stt_manager.create_service(self._service_name, self._config)

    async def transcribe(self, audio: bytes) -> str:
        """The text spoken in *audio*: 16 kHz mono 16-bit PCM, one utterance.

        A session is expected to have called `prepare` before it records, and
        saying it again costs nothing; doing it here as well means a backend used
        without one still transcribes rather than failing on a missing pipeline.
        """
        await self.prepare(lambda _message: None)
        pipeline = self._pipeline
        if pipeline is None:
            raise RuntimeError(f"the {self._service_name} service did not start")
        return await pipeline.transcribe(audio)

    async def aclose(self) -> None:
        """Stop the pipeline and release the service's model.

        Named apart from `close` rather than overloading it, because this is a
        coroutine and its caller is not: `DictationSession.close` is synchronous,
        and a `close` it had to remember to schedule would be a trap.

        Once let go, this backend stays let go: the session that owned it is over,
        and starting a pipeline again for it would be starting one nothing closes.
        A `prepare` already loading a model is not waited for; what it starts after
        this returns hands the pipeline back here rather than adopting it.
        """
        pipeline = self._detach_pipeline()
        if pipeline is not None:
            await pipeline.close()

    def release(self) -> None:
        """Drop the pipeline where no loop is left to stop its worker on.

        `aclose` cannot run here. The worker is a task of the loop this pipeline
        was started on, and awaiting it from another loop raises the cross-loop
        error `close_quietly` swallows, so the pipeline this backend still holds
        would be the one thing a session that has already ended keeps alive: a
        loaded model, and a worker nothing can reach. Letting go is what is left,
        and it is what makes both collectable.
        """
        self._detach_pipeline()

    def _detach_pipeline(self) -> "STTPipeline | None":
        """Take the pipeline off this backend, and mark it let go for good."""
        with self._handoff:
            self._is_closed = True
            pipeline, self._pipeline = self._pipeline, None
            self._loop = None
        return pipeline
