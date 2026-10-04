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
    noise_margin: float | None = None
    silence: float | None = None
    min_silence: float | None = None
    min_speech: float | None = None
    min_words: int | None = None
    max_utterance: float | None = None
    max_backlog: float | None = None
    pre_roll: float | None = None
    barge_in_enabled: bool | None = None
    barge_in_min_speech: float | None = None
    barge_in_margin: float | None = None
    barge_in_min_words: int | None = None
    interrupt_judge_enabled: bool | None = None
    interrupt_judge_model: str | None = None
    approve_words: list[str] | None = None
    deny_words: list[str] | None = None
    stop_words: list[str] | None = None
    polite_words: list[str] | None = None
    device: str | None = None
    block_duration: float | None = None
    pipecat_enabled: bool | None = None
    transcribe_prompt: str | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    google_model: str | None = None
    vosk_model_name: str | None = None
    vosk_model_url: str | None = None
    vosk_download_timeout: float | None = None
    vosk_max_download_mb: float | None = None
    vosk_max_uncompressed_mb: float | None = None
    vosk_max_file_mb: float | None = None
    vosk_max_files: float | None = None
    vosk_confidence: float | None = None

    @property
    def is_barge_in_enabled(self) -> bool:
        """Whether *barge_in_enabled* is set: hands-free hears the user
        while zrb speaks, and a stop word cancels a running turn."""
        return bool(self.barge_in_enabled)

    @property
    def is_pipecat_enabled(self) -> bool:
        """Whether *pipecat_enabled* is set: the captured blocks are handed to
        a Pipecat pipeline as well, which decides nothing yet (ADR-0106)."""
        return bool(self.pipecat_enabled)

    def resolve(self) -> "DictationConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_DICTATION_")
