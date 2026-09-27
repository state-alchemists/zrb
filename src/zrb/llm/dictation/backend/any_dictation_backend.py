from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


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
