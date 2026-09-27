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
        wav_buffer = io.BytesIO(pcm16_to_wav_bytes(audio))
        wav_buffer.name = "audio.wav"
        result = await self._get_client().audio.transcriptions.create(
            model=self._model, file=wav_buffer
        )
        return result.text

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
