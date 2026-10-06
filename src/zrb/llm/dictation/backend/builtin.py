from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.google import GoogleDictationBackend
from zrb.llm.dictation.backend.multimodal import MultimodalDictationBackend
from zrb.llm.dictation.backend.openai import OpenAIDictationBackend
from zrb.llm.dictation.backend.pipecat import PipecatDictationBackend
from zrb.llm.dictation.backend.vosk import VoskDictationBackend
from zrb.llm.voice.registry import stt_registry

if TYPE_CHECKING:
    from zrb.llm.dictation.config import DictationConfig


def get_dictation_backend(
    backend: "str | AnyDictationBackend", config: "DictationConfig"
) -> AnyDictationBackend:
    """*backend* itself, or the one it names, built from the resolved *config*:
    ``vosk``, ``openai``, ``google``, ``multimodal``, or a speech-to-text
    service registered with ``stt_manager`` (``whisper``, ``moonshine``,
    ``funasr``, or one a project registered)."""
    if isinstance(backend, AnyDictationBackend):
        return backend
    name = backend.strip().lower() or "vosk"
    builtin = _get_builtin_backend(name, config)
    if builtin is not None:
        return builtin
    # A Pipecat speech-to-text service, built-in or registered in code. It
    # transcribes through a pipeline of its own, so nothing else about the
    # session changes and the name is resolved by the service's own manager.
    if stt_registry.get(name) is not None:
        return PipecatDictationBackend(name, config)
    raise ValueError(
        f"unknown dictation backend {backend!r}: use vosk, openai, google, "
        f"multimodal, {', '.join(stt_registry.names())}, or an "
        "AnyDictationBackend"
    )


def _get_builtin_backend(
    name: str, config: "DictationConfig"
) -> AnyDictationBackend | None:
    """The hand-rolled backend *name* builds, or ``None`` when *name* is not one.

    ``None`` rather than a raise, because a name that is not a built-in is not
    an error yet: it may be a speech service registered in code, which is what
    the caller asks next.
    """
    if name == "vosk":
        return VoskDictationBackend(
            config.vosk_model_name or "",
            config.vosk_model_url or "",
            config.vosk_download_timeout,
            config.vosk_max_download_mb,
            config.vosk_max_uncompressed_mb,
            config.vosk_max_file_mb,
            config.vosk_max_files,
            confidence=config.vosk_confidence,
        )
    if name == "openai":
        return OpenAIDictationBackend(
            config.openai_model or "",
            base_url=config.openai_base_url or None,
            language=config.language or None,
        )
    if name == "google":
        return GoogleDictationBackend(
            config.google_model or "", instruction=config.transcribe_prompt or None
        )
    if name == "multimodal":
        return MultimodalDictationBackend(instruction=config.transcribe_prompt or None)
    return None
