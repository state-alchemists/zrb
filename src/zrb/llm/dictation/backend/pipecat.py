"""Dictation transcribed by a Pipecat speech-to-text service.

The service is selected by `ZRB_LLM_DICTATION_BACKEND` and registered through
`zrb.llm.voice`; `AnyDictationBackend` returns only its transcript to the session.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.pipecat_stt import STTPipeline
from zrb.llm.util.teardown import close_quietly
from zrb.llm.voice.manager import stt_manager
from zrb.util.async_thread import run_in_daemon

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import NoReturn

    from pipecat.services.stt_service import STTService

    from zrb.llm.dictation.config import DictationConfig


class PipecatDictationBackend(AnyDictationBackend):
    """A dictation backend whose transcription is a Pipecat STT service.

    Pipecat services transcribe finished utterances; `create_stream` returns
    `None` because they do not stream partials.
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

        A stopped pipeline is discarded and replaced; `report` receives progress
        while the service model is loaded.
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
            service = await run_in_daemon(
                self._create_service,
                name="zrb-pipecat-stt-loader",
                on_orphan=self._let_the_service_go,
            )
            loop = asyncio.get_running_loop()
            pipeline = await self._start_the_pipeline(service)
            with self._handoff:
                abandoned = pipeline if self._is_closed else None
                if abandoned is None:
                    self._loop, self._pipeline = loop, pipeline
            if abandoned is not None:
                # The session ended while its model was loading, and the teardown
                # found no pipeline to close: this is the one it would have closed.
                await abandoned.close()
                self._refuse_a_closed_service()

    async def _start_the_pipeline(self, service: "STTService") -> STTPipeline:
        """Start a pipeline for *service*; clean up the service if startup fails.

        The service was loaded off the event loop and has no other owner until
        the pipeline adopts it.
        """
        try:
            return await STTPipeline.start(service)
        except BaseException:
            await close_quietly(
                service.cleanup, f"the {self._service_name} speech service"
            )
            raise

    def _refuse_a_closed_service(self) -> "NoReturn":
        """Refuse a service for a session that has already let this backend go."""
        raise RuntimeError(
            f"the {self._service_name} speech service was let go, and is "
            "not started again for a session that is over"
        )

    def _let_the_service_go(self, service: "STTService") -> None:
        """Clean up a service whose load outlived its session.

        A cancelled load may return a loaded service without a pipeline; close it
        on the waiting loop when available, or run the close on a temporary loop.
        """
        closing = close_quietly(
            service.cleanup, f"the {self._service_name} speech service"
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(closing)
            return
        loop.create_task(closing)

    def _create_service(self) -> "STTService":
        """Create the service off the event loop because its constructor loads
        the model; Pipecat processors acquire loop-bound state when workers start.
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

        `DictationSession.close` is synchronous; a concurrent `prepare` returns
        its newly started pipeline here instead of adopting it.
        """
        pipeline = self._detach_pipeline()
        if pipeline is not None:
            await pipeline.close()

    def release(self) -> None:
        """Drop the pipeline when no loop remains to stop its worker on.

        `aclose` cannot await a worker from another loop, so dropping the
        reference lets the model and worker become collectable.
        """
        self._detach_pipeline()

    def _detach_pipeline(self) -> "STTPipeline | None":
        """Take the pipeline off this backend, and mark it let go for good."""
        with self._handoff:
            self._is_closed = True
            pipeline, self._pipeline = self._pipeline, None
            self._loop = None
        return pipeline
