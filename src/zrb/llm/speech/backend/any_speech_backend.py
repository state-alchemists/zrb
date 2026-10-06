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

    @property
    def needs_zrb_playback(self) -> bool:
        """Whether this backend's speech can only be heard through zrb's own
        playback, leaving `create_utterance` nothing to offer.

        ``False`` by default: a backend that renders audio is also asked to say
        the text through a program of its own when zrb cannot play it. One that
        can do no such thing — a Pipecat speech service is a model and a
        pipeline, and plays nothing — says so here, so the speaker moves the
        sentence to a backend that can instead of asking a question whose only
        answer is a failure."""
        return False

    def close(self) -> None:
        """Let the backend go, when the session that spoke through it is over.

        Does nothing by default. A backend that holds something — a Pipecat
        service holds a model and a running pipeline — releases it here.

        Must not raise, and is not a coroutine: it runs where a session is being
        torn down, on the thread doing the tearing down, and there is nobody left
        for a failure to reach but the log the caller keeps.
        """
