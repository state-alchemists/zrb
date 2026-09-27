from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.speech.backend.utterance import Utterance


class AnySpeechBackend(ABC):
    """Something that can say text aloud.

    Synthesis and playback are separate so a slow cloud request never holds
    the audio lock: only `Utterance.play` runs under it.
    """

    @property
    def name(self) -> str:
        """How the backend is called in logs."""
        return type(self).__name__

    @abstractmethod
    def create_utterance(self, text: str) -> "Utterance":
        """Synthesize *text*. Raise when the backend cannot."""
