from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.speech.backend.audio import SpeechAudio
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

    def create_audio(self, text: str) -> "SpeechAudio | None":
        """Synthesize *text* as raw audio for zrb to play itself, or ``None``
        for a backend that can only play through a program of its own (the
        default). zrb plays audio itself when it can, which lets dictation
        cancel zrb's voice out of the microphone and pause it. Raise when
        synthesis fails."""
        return None
