from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.gemini import GeminiSpeechBackend
from zrb.llm.speech.backend.local_command import LocalCommandBackend
from zrb.llm.speech.backend.openai import OpenAISpeechBackend
from zrb.llm.speech.backend.pipecat import PipecatSpeechBackend
from zrb.llm.speech.backend.termux import TermuxSpeechBackend
from zrb.llm.voice.registry import tts_registry

if TYPE_CHECKING:
    from zrb.llm.speech.config import SpeechConfig


def get_speech_backend(
    backend: "str | AnySpeechBackend", config: "SpeechConfig"
) -> AnySpeechBackend:
    """*backend* itself, or the one it names, built from the resolved *config*:
    ``auto`` (``termux`` on Termux, ``say`` on macOS, else ``espeak-ng``),
    ``termux``, ``say``, ``espeak-ng``, ``openai``, ``gemini``, or a
    text-to-speech service registered with ``tts_manager`` (``kokoro``,
    ``piper``, ``pocket``, or one a project registered)."""
    if isinstance(backend, AnySpeechBackend):
        return backend
    name = backend.strip().lower() or "auto"
    if name == "auto":
        name = _get_local_backend_name()
    create = _BUILTIN_BACKENDS.get(name)
    if create is not None:
        return create(config)
    # A Pipecat text-to-speech service, built-in or registered in code. It
    # renders audio for zrb to play rather than playing it through a program, so
    # it is a backend here only where zrb can play it itself.
    if tts_registry.get(name) is not None:
        return PipecatSpeechBackend(name, config)
    raise ValueError(
        f"unknown speech backend {backend!r}: use auto, termux, say, espeak-ng, "
        f"openai, gemini, {', '.join(tts_registry.names())}, or an AnySpeechBackend"
    )


def _get_local_backend_name() -> str:
    # lazy: tests patch zrb.config.helper.is_termux; hoisting would bind the
    # name at this module's load time and bypass the mock.
    from zrb.config.helper import is_termux

    if is_termux() and shutil.which("termux-tts-speak"):
        return "termux"
    return "say" if shutil.which("say") else "espeak-ng"


def _create_termux(config: "SpeechConfig") -> AnySpeechBackend:
    return TermuxSpeechBackend(
        language=config.termux_language or None,
        voice_name=config.voice or None,
        engine=config.termux_engine or None,
        region=config.termux_region or None,
        rate=config.termux_rate,
        pitch=config.termux_pitch,
        stream=config.termux_stream or None,
    )


def _create_say(config: "SpeechConfig") -> AnySpeechBackend:
    return LocalCommandBackend(
        "say",
        "-r",
        config.voice or "",
        config.rate or 0,
        render_timeout=config.render_timeout,
    )


def _create_espeak(config: "SpeechConfig") -> AnySpeechBackend:
    voice = config.voice or "en-us+m3"
    return LocalCommandBackend(
        "espeak-ng", "-s", voice, config.rate or 0, render_timeout=config.render_timeout
    )


def _create_openai(config: "SpeechConfig") -> AnySpeechBackend:
    return OpenAISpeechBackend(
        voice=config.voice or "alloy",
        model=config.openai_model or "",
        base_url=config.openai_base_url or "",
        timeout=config.timeout or None,
        wav_player=config.wav_player or "",
        style=config.style or "",
        stall_timeout=config.stall_timeout,
    )


def _create_gemini(config: "SpeechConfig") -> AnySpeechBackend:
    return GeminiSpeechBackend(
        voice=config.voice or "Sulafat",
        model=config.gemini_model or "",
        timeout=config.timeout or None,
        wav_player=config.wav_player or "",
        style=config.style or "",
        prompt=config.gemini_prompt,
        style_prompt=config.gemini_style_prompt,
    )


_BUILTIN_BACKENDS: dict[str, Callable[["SpeechConfig"], AnySpeechBackend]] = {
    "termux": _create_termux,
    "say": _create_say,
    "espeak-ng": _create_espeak,
    "openai": _create_openai,
    "gemini": _create_gemini,
}
