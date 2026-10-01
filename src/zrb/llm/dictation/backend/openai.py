from __future__ import annotations

import io
import os

from zrb.config.config import CFG
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.wav import pcm16_to_wav_bytes


class OpenAIDictationBackend(AnyDictationBackend):
    """OpenAI's transcription API (whisper-1, gpt-4o-transcribe, ...)."""

    def __init__(
        self,
        model: str = "whisper-1",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    async def transcribe(self, audio: bytes) -> str:
        """*audio*'s words. A Whisper model also says how sure it is of each
        segment, and a segment that is likely no speech, or one phrase over
        and over, is left out: Whisper writes words for noise."""
        wav_buffer = io.BytesIO(pcm16_to_wav_bytes(audio))
        wav_buffer.name = "audio.wav"
        transcriptions = self._get_client().audio.transcriptions
        if not self._model.startswith("whisper"):
            result = await transcriptions.create(model=self._model, file=wav_buffer)
            return result.text
        result = await transcriptions.create(
            model=self._model, file=wav_buffer, response_format="verbose_json"
        )
        segments = getattr(result, "segments", None)
        # A compatible server may leave the segments out.
        if not isinstance(segments, list) or not segments:
            return result.text
        return " ".join(
            segment.text.strip() for segment in segments if _is_speech(segment)
        ).strip()

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            # lazy: heavy third-party
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai is not installed. pip install openai.") from None
        api_key = self._api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it, or switch backends: "
                f"{CFG.ENV_PREFIX}_LLM_DICTATION_BACKEND=vosk|google|multimodal."
            )
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._base_url)
        return self._client


# Whisper's own signs that a segment is not speech, as the Whisper project
# uses them: likely silence the model is unsure of, or text so repetitive it
# compresses well.
_NO_SPEECH_PROB = 0.6
_LOW_LOGPROB = -1.0
_REPETITIVE_COMPRESSION = 2.4


def _is_speech(segment: object) -> bool:
    no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
    logprob = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
    compression = float(getattr(segment, "compression_ratio", 0.0) or 0.0)
    if no_speech > _NO_SPEECH_PROB and logprob < _LOW_LOGPROB:
        return False
    return compression <= _REPETITIVE_COMPRESSION
