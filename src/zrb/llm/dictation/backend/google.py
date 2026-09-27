from __future__ import annotations

import asyncio
import os

from zrb.config.config import CFG
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.wav import pcm16_to_wav_bytes

TRANSCRIBE_INSTRUCTION = "Transcribe this audio to text. Return only the transcription."


class GoogleDictationBackend(AnyDictationBackend):
    """Google Gemini, asked to transcribe."""

    def __init__(
        self, model: str = "gemini-2.5-flash", api_key: str | None = None
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._client = None

    @property
    def name(self) -> str:
        return "google"

    async def transcribe(self, audio: bytes) -> str:
        client = self._get_client()
        # lazy: heavy third-party; after the client, which reports it missing
        from google.genai import types

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self._model,
            contents=[
                types.Part.from_bytes(
                    data=pcm16_to_wav_bytes(audio), mime_type="audio/wav"
                ),
                TRANSCRIBE_INSTRUCTION,
            ],
        )
        return response.text.strip() if response.text else ""

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            # lazy: heavy third-party
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai is not installed. pip install google-genai."
            ) from None
        api_key = (
            self._api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY", "")
        )
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. Set one, or switch "
                f"backends: {CFG.ENV_PREFIX}_LLM_DICTATION_BACKEND=vosk|openai|multimodal."
            )
        self._client = genai.Client(api_key=api_key)
        return self._client
