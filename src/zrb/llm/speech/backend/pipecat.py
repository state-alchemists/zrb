"""Speech synthesized by a Pipecat service and played by zrb."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from zrb.llm.ambient_state import get_current_speech_voice
from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.voice.manager import tts_manager
from zrb.llm.voice.registry import tts_registry

if TYPE_CHECKING:
    from zrb.llm.speech.backend.audio import SpeechAudio
    from zrb.llm.speech.backend.utterance import Utterance
    from zrb.llm.speech.config import SpeechConfig
    from zrb.llm.speech.pipecat_tts import TTSPipeline

# How long a sentence waits for another thread's model load before giving up
# and letting the speaker fall back. A first local load downloads its model, so
# this is generous: what it is here to prevent is silence, not slowness.
PIPELINE_START_TIMEOUT_SECONDS = 120.0


class PipecatSpeechBackend(AnySpeechBackend):
    """A cached Pipecat service whose audio zrb plays."""

    def __init__(self, service_name: str, config: "SpeechConfig") -> None:
        self._service_name = service_name
        self._config = config
        self._pipeline: TTSPipeline | None = None
        # Serializes starting the pipeline, which can take as long as a model
        # download; `close` never waits for it.
        self._starting = threading.Lock()
        # Guards `_pipeline` and `_is_closed`, held only briefly.
        self._state = threading.Lock()
        self._is_closed = False

    @property
    def name(self) -> str:
        """How the backend is called in logs."""
        return f"Pipecat ({self._service_name})"

    @property
    def needs_zrb_playback(self) -> bool:
        """Whether this service requires zrb playback."""
        return True

    @property
    def is_local(self) -> bool:
        """Whether the registered service runs on this machine."""
        spec = tts_registry.get(self._service_name)
        return spec is not None and spec.is_local

    def create_utterance(self, text: str) -> "Utterance":
        """Reject playback through an external player program."""
        raise RuntimeError(
            f"the {self._service_name} speech service renders audio for zrb to "
            "play in process, and cannot play it through a program of its own"
        )

    def create_audio(self, text: str) -> "SpeechAudio":
        """Return *text* as PCM for in-process playback, in the voice the
        speaker asks for, else the one the service was built with."""
        return self._get_pipeline().speak(text, voice=get_current_speech_voice())

    def close(self) -> None:
        """Stop and discard the pipeline. A pipeline still starting is not
        waited for: it closes itself once it has started."""
        with self._state:
            self._is_closed = True
            pipeline, self._pipeline = self._pipeline, None
        if pipeline is not None:
            pipeline.close()

    def _get_pipeline(self) -> "TTSPipeline":
        """Return the cached pipeline, starting it on first use.

        The start is where a local service loads its model, and waiting for it
        used to be unbounded: a load that never finished parked every sentence
        behind it and the session went silent with no error at all. A start
        that overruns is given up on instead, so the speaker falls back to a
        voice that is audible.
        """
        if not self._starting.acquire(timeout=PIPELINE_START_TIMEOUT_SECONDS):
            raise RuntimeError(
                f"the {self._service_name} speech service is still starting "
                f"after {PIPELINE_START_TIMEOUT_SECONDS:g}s"
            )
        try:
            with self._state:
                pipeline, is_closed = self._pipeline, self._is_closed
            if is_closed:
                raise self._closed_error()
            if pipeline is None:
                pipeline = self._start_pipeline()
            return pipeline
        finally:
            self._starting.release()

    def _start_pipeline(self) -> "TTSPipeline":
        # lazy: circular — defer the pipeline import until first use.
        from zrb.llm.speech.pipecat_tts import TTSPipeline

        service = tts_manager.create_service(self._service_name, self._config)
        pipeline = TTSPipeline.start(service)
        with self._state:
            is_closed = self._is_closed
            if not is_closed:
                self._pipeline = pipeline
        if is_closed:
            pipeline.close()
            raise self._closed_error()
        return pipeline

    def _closed_error(self) -> RuntimeError:
        return RuntimeError(f"the {self._service_name} speech service was closed")
