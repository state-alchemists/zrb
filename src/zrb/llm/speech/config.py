from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.util.feature_config import resolve_from_cfg

if TYPE_CHECKING:
    from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend


@dataclass
class SpeechConfig:
    """Settings for `enable_speech`. Each field mirrors `CFG.LLM_SPEECH_<FIELD>`;
    one left ``None`` is read from there when a session starts.

    *backend* names a built-in backend (``auto``, ``termux``, ``say``,
    ``espeak-ng``, ``openai``, ``gemini``), built from the fields here, or is
    an `AnySpeechBackend` of your own, which ignores them.
    """

    enabled: bool | None = None
    commands: list[str] | None = None
    backend: "str | AnySpeechBackend | None" = None
    voice: str | None = None
    style: str | None = None
    rate: int | None = None
    max_chars: int | None = None
    summarize: bool | None = None
    stream: bool | None = None
    progress_interval: float | None = None
    summary_model: str | None = None
    on_screen_note: str | None = None
    events: list[str] | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    gemini_model: str | None = None
    termux_language: str | None = None
    termux_engine: str | None = None
    termux_region: str | None = None
    termux_rate: float | None = None
    termux_pitch: float | None = None
    termux_stream: str | None = None
    timeout: float | None = None
    wav_player: str | None = None
    player: str | None = None
    lock_file: str | None = None
    lock_timeout: float | None = None
    drain_timeout: float | None = None
    player_timeout: float | None = None

    def resolve(self) -> "SpeechConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_SPEECH_")
