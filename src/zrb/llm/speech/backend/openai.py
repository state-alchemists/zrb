from __future__ import annotations

from typing import BinaryIO

from zrb.config.config import CFG
from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.audio import SpeechAudio, create_streamed_wav_audio
from zrb.llm.speech.backend.http import get_required_env, open_post_json
from zrb.llm.speech.backend.utterance import (
    Utterance,
    create_streamed_wav_utterance,
    shut_down_socket,
)


class OpenAISpeechBackend(AnySpeechBackend):
    """OpenAI's /audio/speech endpoint, or any API compatible with it.

    The key is *api_key*, else ``OPENAI_API_KEY``. *style* directs how the
    voice sounds (the API's ``instructions``); the ``tts-1`` models do not
    take one, so it is left out for them. With no *timeout*, audio that
    stops arriving for *stall_timeout* seconds (default:
    `CFG.LLM_SPEECH_STALL_TIMEOUT`) is given up on.
    """

    def __init__(
        self,
        voice: str = "alloy",
        model: str = "gpt-4o-mini-tts",
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout: float | None = None,
        wav_player: str = "",
        style: str = "",
        stall_timeout: float | None = None,
    ) -> None:
        self._stall_timeout = stall_timeout
        self._voice = voice
        self._style = style
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout
        self._wav_player = wav_player

    @property
    def name(self) -> str:
        return "openai"

    def create_utterance(self, text: str) -> Utterance:
        return create_streamed_wav_utterance(self._request(text), self._wav_player)

    def create_audio(self, text: str) -> SpeechAudio:
        response = self._request(text)
        try:
            return create_streamed_wav_audio(response, lambda: _close(response))
        except BaseException:
            response.close()
            raise

    def _request(self, text: str) -> BinaryIO:
        key = self._api_key or get_required_env("OPENAI_API_KEY")
        body = {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "response_format": "wav",
        }
        if self._style and not self._model.startswith("tts-1"):
            body["instructions"] = self._style
        url = f"{self._base_url.rstrip('/')}/audio/speech"
        headers = {"Authorization": f"Bearer {key}"}
        stall = self._stall_timeout
        if stall is None:
            stall = CFG.LLM_SPEECH_STALL_TIMEOUT
        # The audio is read after `create_utterance` returns, on a thread
        # nothing can interrupt, so a server that stops sending must not hold
        # it open forever.
        timeout = self._timeout or stall or None
        return open_post_json(url, body, headers, timeout)


def _close(response: BinaryIO) -> None:
    """Close a download, ending a read blocked on it from another thread."""
    shut_down_socket(response)
    try:
        response.close()
    except OSError:
        pass
