from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from zrb.llm.dictation.backend.any_transcription_stream import AnyTranscriptionStream


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

    async def create_stream(self) -> AnyTranscriptionStream | None:
        """A stream transcribing one utterance while it is spoken, or ``None``
        for a backend that only transcribes a finished utterance (the
        default). Hands-free uses a stream when it gets one: the transcript is
        ready sooner, and the utterance can end sooner once it sounds done."""
        return None
