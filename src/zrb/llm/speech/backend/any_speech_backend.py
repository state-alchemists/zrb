from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.speech.backend.audio import SpeechAudio
    from zrb.llm.speech.backend.utterance import Utterance


class AnySpeechBackend(ABC):
    """Interface for text-to-speech backends."""

    @property
    def name(self) -> str:
        """How the backend is called in logs."""
        return type(self).__name__

    @abstractmethod
    def create_utterance(self, text: str) -> "Utterance":
        """Synthesize *text*. Raise when the backend cannot."""

    def create_audio(self, text: str) -> "SpeechAudio | None":
        """Synthesize *text* as raw audio, or return ``None``."""
        return None

    @property
    def needs_zrb_playback(self) -> bool:
        """Whether the backend requires zrb's own playback."""
        return False

    def close(self) -> None:
        """Release backend resources during session teardown."""
