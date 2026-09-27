from __future__ import annotations

import base64
import json
import os

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.http import get_required_env, pcm_to_wav, post_json
from zrb.llm.speech.backend.utterance import Utterance, create_wav_utterance


class GeminiSpeechBackend(AnySpeechBackend):
    """Gemini text-to-speech via generateContent.

    The key is *api_key*, else ``GEMINI_API_KEY``, else ``GOOGLE_API_KEY``.
    """

    def __init__(
        self,
        voice: str = "Sulafat",
        model: str = "gemini-2.5-flash-preview-tts",
        api_key: str | None = None,
        timeout: float | None = None,
        wav_player: str = "",
    ) -> None:
        self._voice = voice
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._wav_player = wav_player

    @property
    def name(self) -> str:
        return "gemini"

    def create_utterance(self, text: str) -> Utterance:
        key = (
            self._api_key
            or os.getenv("GEMINI_API_KEY")
            or get_required_env("GOOGLE_API_KEY")
        )
        body = {
            # Without "Say:", Gemini may answer a short line instead of reading it.
            "contents": [{"parts": [{"text": f"Say: {text}"}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self._voice}}
                },
            },
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        reply = json.loads(post_json(url, body, {"x-goog-api-key": key}, self._timeout))
        parts = reply["candidates"][0]["content"]["parts"]
        pcm = b"".join(
            base64.b64decode(part["inlineData"]["data"])
            for part in parts
            if "inlineData" in part
        )
        if not pcm:
            # A text or safety reply: raising lets the local engine speak.
            raise RuntimeError(
                "Gemini returned no audio for this text; falling back to local speech"
            )
        return create_wav_utterance(pcm_to_wav(pcm), self._wav_player)
