from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.util.feature_config import resolve_from_cfg

if TYPE_CHECKING:
    from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend


@dataclass
class DictationConfig:
    """Settings for `enable_dictation`. Each field mirrors
    `CFG.LLM_DICTATION_<FIELD>`; one left ``None`` is read from there when a
    session starts.

    *backend* names a built-in backend (``vosk``, ``openai``, ``google``,
    ``multimodal``) or is an `AnyDictationBackend` of your own.
    """

    mode: str | None = None
    commands: list[str] | None = None
    hands_free_commands: list[str] | None = None
    backend: "str | AnyDictationBackend | None" = None
    wake_words: list[str] | None = None
    wake_window: float | None = None
    threshold: float | None = None
    silence: float | None = None
    min_speech: float | None = None
    max_utterance: float | None = None
    pre_roll: float | None = None
    echo_cooldown: float | None = None
    approve_words: list[str] | None = None
    deny_words: list[str] | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    google_model: str | None = None
    vosk_model_name: str | None = None
    vosk_model_url: str | None = None
    vosk_download_timeout: float | None = None

    def resolve(self) -> "DictationConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_DICTATION_")
