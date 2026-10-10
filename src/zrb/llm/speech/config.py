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

    A *summarize_above_chars* above 0 has the small model summarize a reply
    longer than that, once it is finished, and speaks the summary instead; it
    also turns off sentence streaming of the reply, which cannot be summarized
    while it is still being written.
    """

    enabled: bool | None = None
    commands: list[str] | None = None
    backend: "str | AnySpeechBackend | None" = None
    voice: str | None = None
    style: str | None = None
    rate: int | None = None
    stream: bool | None = None
    summarize_above_chars: int | None = None
    summary_model: str | None = None
    summary_timeout: float | None = None
    progress_interval: float | None = None
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
    question_message: str | None = None
    approval_message: str | None = None
    approval_target_keys: list[str] | None = None
    approval_target_max_chars: int | None = None
    progress_silent_tools: list[str] | None = None
    gemini_prompt: str | None = None
    gemini_style_prompt: str | None = None
    render_timeout: float | None = None
    stall_timeout: float | None = None
    player_block_frames: int | None = None
    player_read_ahead: int | None = None
    progress_phrases: dict[str, str] | None = None
    approval_actions: dict[str, str] | None = None

    def resolve(self) -> "SpeechConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_SPEECH_")
