from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.gemini import GeminiSpeechBackend
from zrb.llm.speech.backend.local_command import LocalCommandBackend
from zrb.llm.speech.backend.openai import OpenAISpeechBackend

if TYPE_CHECKING:
    from zrb.llm.speech.config import SpeechConfig


def get_speech_backend(
    backend: "str | AnySpeechBackend", config: "SpeechConfig"
) -> AnySpeechBackend:
    """*backend* itself, or the built-in one it names, built from the
    resolved *config*: ``auto`` (``say`` on macOS, else ``espeak-ng``),
    ``say``, ``espeak-ng``, ``openai`` or ``gemini``."""
    if isinstance(backend, AnySpeechBackend):
        return backend
    name = backend.strip().lower() or "auto"
    if name == "auto":
        name = "say" if shutil.which("say") else "espeak-ng"
    create = _BUILTIN_BACKENDS.get(name)
    if create is None:
        raise ValueError(
            f"unknown speech backend {backend!r}: use auto, say, espeak-ng, "
            "openai, gemini, or an AnySpeechBackend"
        )
    return create(config)


def _create_say(config: "SpeechConfig") -> AnySpeechBackend:
    return LocalCommandBackend("say", "-r", config.voice or "", config.rate or 0)


def _create_espeak(config: "SpeechConfig") -> AnySpeechBackend:
    voice = config.voice or "en-us+m3"
    return LocalCommandBackend("espeak-ng", "-s", voice, config.rate or 0)


def _create_openai(config: "SpeechConfig") -> AnySpeechBackend:
    return OpenAISpeechBackend(
        voice=config.voice or "alloy",
        model=config.openai_model or "",
        base_url=config.openai_base_url or "",
        timeout=config.timeout,
        wav_player=config.wav_player or "",
    )


def _create_gemini(config: "SpeechConfig") -> AnySpeechBackend:
    return GeminiSpeechBackend(
        voice=config.voice or "Sulafat",
        model=config.gemini_model or "",
        timeout=config.timeout,
        wav_player=config.wav_player or "",
    )


_BUILTIN_BACKENDS: dict[str, Callable[["SpeechConfig"], AnySpeechBackend]] = {
    "say": _create_say,
    "espeak-ng": _create_espeak,
    "openai": _create_openai,
    "gemini": _create_gemini,
}
