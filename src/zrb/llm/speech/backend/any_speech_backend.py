from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.speech.backend.audio import SpeechAudio
    from zrb.llm.speech.backend.utterance import Utterance


class SpeechServiceStopped(RuntimeError):
    """A backend's speech service stopped making audio for good.

    Not the same as a sentence that failed. A service Pipecat marks unusable
    refuses every sentence it is given from then on, so a backend holding one
    has to let it go and start a fresh service rather than keep asking: the
    alternative is a session that goes mute while every sentence is reported
    as one more failed render."""


class SpeechMadeNoAudio(RuntimeError):
    """A backend's service made no audio at all for one sentence.

    The first chunk never arrived, so not a word of that sentence was said. Not
    the same as a service that stopped: this pipeline may well speak the next
    sentence, but it has already made nothing of this one, and asking it again
    is how a sentence is lost. A backend that hears this lets the pipeline go,
    so the caller's next attempt — the speaker asks a local voice twice — is a
    fresh service, which is what speaks a sentence this one made nothing of."""


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

    @property
    def is_local(self) -> bool:
        """Whether the backend synthesizes on this machine, not a paid API."""
        return False

    def close(self) -> None:
        """Release backend resources during session teardown."""
