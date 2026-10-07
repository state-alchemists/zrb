"""Speech synthesized by a Pipecat service and played by zrb."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.voice.manager import tts_manager

if TYPE_CHECKING:
    from zrb.llm.speech.backend.audio import SpeechAudio
    from zrb.llm.speech.backend.utterance import Utterance
    from zrb.llm.speech.config import SpeechConfig
    from zrb.llm.speech.pipecat_tts import TTSPipeline


class PipecatSpeechBackend(AnySpeechBackend):
    """A cached Pipecat service whose audio zrb plays."""

    def __init__(self, service_name: str, config: "SpeechConfig") -> None:
        self._service_name = service_name
        self._config = config
        self._pipeline: TTSPipeline | None = None
        # Serialize lazy pipeline creation.
        self._starting = threading.Lock()
        self._is_closed = False

    @property
    def name(self) -> str:
        """How the backend is called in logs."""
        return f"Pipecat ({self._service_name})"

    @property
    def needs_zrb_playback(self) -> bool:
        """Whether this service requires zrb playback."""
        return True

    def create_utterance(self, text: str) -> "Utterance":
        """Reject playback through an external player program."""
        raise RuntimeError(
            f"the {self._service_name} speech service renders audio for zrb to "
            "play in process, and cannot play it through a program of its own"
        )

    def create_audio(self, text: str) -> "SpeechAudio":
        """Return *text* as PCM for in-process playback."""
        return self._get_pipeline().speak(text)

    def close(self) -> None:
        """Stop and discard the pipeline."""
        with self._starting:
            self._is_closed = True
            pipeline, self._pipeline = self._pipeline, None
        if pipeline is not None:
            pipeline.close()

    def _get_pipeline(self) -> "TTSPipeline":
        """Return the cached pipeline, starting it on first use."""
        # lazy: circular — defer the pipeline import until first use.
        from zrb.llm.speech.pipecat_tts import TTSPipeline

        with self._starting:
            if self._is_closed:
                raise RuntimeError(
                    f"the {self._service_name} speech service was closed"
                )
            if self._pipeline is None:
                service = tts_manager.create_service(self._service_name, self._config)
                self._pipeline = TTSPipeline.start(service)
            return self._pipeline
