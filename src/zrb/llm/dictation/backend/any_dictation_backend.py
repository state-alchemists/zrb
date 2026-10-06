from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_transcription_stream import AnyTranscriptionStream

if TYPE_CHECKING:
    import asyncio


class AnyDictationBackend(ABC):
    """A speech-to-text service for dictation."""

    @property
    def name(self) -> str:
        """How the backend is called in messages."""
        return type(self).__name__

    async def prepare(self, report: Callable[[str], None]) -> None:
        """Get ready before the first recording (e.g. download a model),
        passing progress to *report*. Nothing to do by default."""

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """The text spoken in *audio*: 16 kHz mono 16-bit PCM."""

    async def transcribe_speech(self, audio: bytes) -> str:
        """As `transcribe`, without text the backend scores as made up from
        noise. Used by hands-free; push-to-talk uses `transcribe`. Defaults
        to `transcribe`."""
        return await self.transcribe(audio)

    async def create_stream(self) -> AnyTranscriptionStream | None:
        """A stream transcribing one utterance while it is spoken, or ``None``
        for a backend that only transcribes a finished utterance (the
        default). Hands-free uses a stream when it gets one: the transcript is
        ready sooner, and the utterance can end sooner once it sounds done."""
        return None

    @property
    def owner_loop(self) -> "asyncio.AbstractEventLoop | None":
        """The loop this backend is bound to, or ``None`` when it holds nothing
        a loop owns.

        A backend that started a pipeline holds a worker task only the loop that
        started it can await or cancel, and a session's teardown is synchronous,
        so it may not be running there. `DictationSession.close` is what asks, to
        let the backend go where letting go works rather than on a loop of its
        own, where awaiting that task fails and the pipeline runs on."""
        return None

    async def aclose(self) -> None:
        """Release what this backend holds, for a session that is over.

        Nothing to do by default. A backend that holds a model, a device or a
        running pipeline is what this exists for, and it is asynchronous where
        the session's own teardown is not, so it is named apart from `close`
        rather than overloading it."""
