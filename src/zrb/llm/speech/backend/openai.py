from __future__ import annotations

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.http import get_required_env, post_json
from zrb.llm.speech.backend.utterance import Utterance, create_wav_utterance


class OpenAISpeechBackend(AnySpeechBackend):
    """OpenAI's /audio/speech endpoint, or any API compatible with it.

    The key is *api_key*, else ``OPENAI_API_KEY``.
    """

    def __init__(
        self,
        voice: str = "alloy",
        model: str = "gpt-4o-mini-tts",
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout: float | None = None,
        wav_player: str = "",
    ) -> None:
        self._voice = voice
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout
        self._wav_player = wav_player

    @property
    def name(self) -> str:
        return "openai"

    def create_utterance(self, text: str) -> Utterance:
        key = self._api_key or get_required_env("OPENAI_API_KEY")
        body = {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "response_format": "wav",
        }
        url = f"{self._base_url.rstrip('/')}/audio/speech"
        wav = post_json(url, body, {"Authorization": f"Bearer {key}"}, self._timeout)
        return create_wav_utterance(wav, self._wav_player)
