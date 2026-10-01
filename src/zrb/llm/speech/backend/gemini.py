from __future__ import annotations

import base64
import json
import os

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.backend.http import get_required_env, pcm_to_wav, post_json
from zrb.config.config import CFG
from zrb.llm.speech.backend.utterance import Utterance, create_wav_utterance
from zrb.llm.speech.text import fill_template

_SAMPLE_RATE = 24000


class GeminiSpeechBackend(AnySpeechBackend):
    """Gemini text-to-speech via generateContent.

    The key is *api_key*, else ``GEMINI_API_KEY``, else ``GOOGLE_API_KEY``.
    *style* directs how the voice sounds; Gemini takes it as part of the
    prompt, ahead of the text to read. *prompt* (no style) and
    *style_prompt* wrap the text, as ``{text}`` and ``{style}``; left
    ``None``, `CFG.LLM_SPEECH_GEMINI_PROMPT` and
    `CFG.LLM_SPEECH_GEMINI_STYLE_PROMPT`.
    """

    def __init__(
        self,
        voice: str = "Sulafat",
        model: str = "gemini-2.5-flash-preview-tts",
        api_key: str | None = None,
        timeout: float | None = None,
        wav_player: str = "",
        style: str = "",
        prompt: str | None = None,
        style_prompt: str | None = None,
    ) -> None:
        self._voice = voice
        self._style = style
        self._prompt = prompt
        self._style_prompt = style_prompt
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._wav_player = wav_player

    @property
    def name(self) -> str:
        return "gemini"

    def create_utterance(self, text: str) -> Utterance:
        return create_wav_utterance(
            pcm_to_wav(self._synthesize(text)), self._wav_player
        )

    def create_audio(self, text: str) -> SpeechAudio:
        return SpeechAudio(_SAMPLE_RATE, [self._synthesize(text)])

    def _synthesize(self, text: str) -> bytes:
        """*text* as 16-bit mono PCM at 24 kHz."""
        key = (
            self._api_key
            or os.getenv("GEMINI_API_KEY")
            or get_required_env("GOOGLE_API_KEY")
        )
        body = {
            "contents": [{"parts": [{"text": self._create_prompt(text)}]}],
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
        return pcm

    def _create_prompt(self, text: str) -> str:
        # Without an instruction ("Say:"), Gemini may answer a short line
        # instead of reading it.
        if not self._style:
            prompt = self._prompt
            if prompt is None:
                prompt = CFG.LLM_SPEECH_GEMINI_PROMPT
            return fill_template(prompt, text=text)
        style_prompt = self._style_prompt
        if style_prompt is None:
            style_prompt = CFG.LLM_SPEECH_GEMINI_STYLE_PROMPT
        return fill_template(style_prompt, style=self._style, text=text)
