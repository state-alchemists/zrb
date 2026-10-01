from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.google import GoogleDictationBackend
from zrb.llm.dictation.backend.multimodal import MultimodalDictationBackend
from zrb.llm.dictation.backend.openai import OpenAIDictationBackend
from zrb.llm.dictation.backend.vosk import VoskDictationBackend

if TYPE_CHECKING:
    from zrb.llm.dictation.config import DictationConfig


def get_dictation_backend(
    backend: "str | AnyDictationBackend", config: "DictationConfig"
) -> AnyDictationBackend:
    """*backend* itself, or the built-in one it names, built from the resolved
    *config*: ``vosk``, ``openai``, ``google`` or ``multimodal``."""
    if isinstance(backend, AnyDictationBackend):
        return backend
    name = backend.strip().lower() or "vosk"
    if name == "vosk":
        return VoskDictationBackend(
            config.vosk_model_name or "",
            config.vosk_model_url or "",
            config.vosk_download_timeout,
            config.vosk_max_download_mb,
            config.vosk_max_uncompressed_mb,
            config.vosk_max_file_mb,
            config.vosk_max_files,
        )
    if name == "openai":
        return OpenAIDictationBackend(
            config.openai_model or "", base_url=config.openai_base_url or None
        )
    if name == "google":
        return GoogleDictationBackend(
            config.google_model or "", instruction=config.transcribe_prompt or None
        )
    if name == "multimodal":
        return MultimodalDictationBackend(instruction=config.transcribe_prompt or None)
    raise ValueError(
        f"unknown dictation backend {backend!r}: use vosk, openai, google, "
        "multimodal, or an AnyDictationBackend"
    )
