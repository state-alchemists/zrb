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
from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.pipecat_stt import STTPipeline
from zrb.llm.voice.manager import stt_manager

if TYPE_CHECKING:
    from collections.abc import Callable

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
        # `prepare` is called again for every recording, not only the first, so
        # the look-then-build has to be one step: two callers that both found no
        # pipeline would build two models.
        self._preparing = asyncio.Lock()

    @property
    def name(self) -> str:
        """How the backend is called in messages."""
        return f"Pipecat ({self._service_name})"

    async def prepare(self, report: "Callable[[str], None]") -> None:
        """Load the service and start its pipeline, at most once.

        `report` hears about it first: a model is downloaded or read from disk
        here, which on a first run is the longest wait in the session.
        """
        async with self._preparing:
            if self._pipeline is not None:
                return
            report(f"Loading the {self._service_name} speech service…")
            service = await asyncio.to_thread(self._create_service)
            self._pipeline = await STTPipeline.start(service)

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
        """
        pipeline, self._pipeline = self._pipeline, None
        if pipeline is not None:
            await pipeline.close()
