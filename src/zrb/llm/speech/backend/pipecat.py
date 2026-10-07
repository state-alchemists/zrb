"""Speech synthesized by a Pipecat text-to-speech service.

The service is the one `zrb.llm.voice` builds from the name the config gives
(`ZRB_LLM_SPEECH_BACKEND`) — `kokoro`, `piper`, `pocket`, or one a project
registered in `zrb_init.py` — so what a session speaks through is a setting, and
the voices are Pipecat's rather than zrb's.

Playback is not Pipecat's. `create_audio` hands zrb the raw PCM as the service
makes it, and zrb plays it through an output stream of its own (ADR-0103): that is
what lets dictation cancel zrb's own voice out of the microphone, hold it
mid-sentence for a user who may be talking, and leave a sentence that was cut off
cut off. A backend that could only play through a program of its own could do none
of that, so this one refuses `create_utterance` and the speaker says the sentence
through the local voice instead — espeak or `say` — rather than say nothing.
"""

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
    """Speech a Pipecat text-to-speech service says, played by zrb.

    The service and its pipeline are built on first use and kept for the life of
    the backend, because the expensive part is the model a service loads in its
    constructor: one built per sentence would pay for the model per sentence.
    """

    def __init__(self, service_name: str, config: "SpeechConfig") -> None:
        self._service_name = service_name
        self._config = config
        self._pipeline: TTSPipeline | None = None
        # The speaker prepares a sentence while the one before it plays, so two
        # callers can arrive together: the look-then-build has to be one step, or
        # both would build a pipeline and load the model twice.
        self._starting = threading.Lock()
        self._is_closed = False

    @property
    def name(self) -> str:
        """How the backend is called in logs."""
        return f"Pipecat ({self._service_name})"

    @property
    def needs_zrb_playback(self) -> bool:
        """True: this service renders audio and plays nothing itself.

        `create_utterance` raises, which is what puts a sentence zrb cannot play
        in process — no output device, or a player program configured — onto the
        local voice instead of leaving it unsaid.
        """
        return True

    def create_utterance(self, text: str) -> "Utterance":
        """Refused: this service renders audio, and plays nothing itself.

        Raising is what tells the speaker to say the sentence through the local
        voice instead; the alternative would be a sentence nobody hears.
        """
        raise RuntimeError(
            f"the {self._service_name} speech service renders audio for zrb to "
            "play in process, and cannot play it through a program of its own"
        )

    def create_audio(self, text: str) -> "SpeechAudio":
        """*text* as PCM the player reads while it plays it.

        The wait for a local model to start saying something is the pipeline's own
        (`FIRST_CHUNK_TIMEOUT_SECONDS`), not ``LLM_SPEECH_TIMEOUT``: that one is how
        long a *cloud* backend may take, and a model being fetched or loaded the
        first time deserves longer than a request does.
        """
        return self._get_pipeline().speak(text)

    def close(self) -> None:
        """Stop the pipeline, releasing the service's model; none is started after."""
        with self._starting:
            self._is_closed = True
            pipeline, self._pipeline = self._pipeline, None
        if pipeline is not None:
            pipeline.close()

    def _get_pipeline(self) -> "TTSPipeline":
        """The running pipeline, started on first use and then kept."""
        # lazy: circular — the speech backend package re-exports every backend, so
        # importing the pipeline at this module's own load time would put this
        # module's package in the middle of the pipeline's import. Deferring it to
        # the first sentence, where the pipeline is built anyway, is the whole cost.
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
