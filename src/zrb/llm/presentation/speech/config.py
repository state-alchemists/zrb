from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.contracts.shared.feature_config import (
    accepts_renamed_fields,
    resolve_from_cfg,
)

if TYPE_CHECKING:
    from zrb.llm.presentation.speech.backend.any_speech_backend import AnySpeechBackend


@accepts_renamed_fields(missing_block_notice_enabled="block_notice_enabled")
@dataclass(kw_only=True)
class SpeechConfig:
    """Settings for `enable_speech`. Each field mirrors `CFG.LLM_SPEECH_<FIELD>`;
    one left ``None`` is read from there when a session starts.

    *block_notice_enabled* tells the model, on the turn after one, that its last
    reply opened no spoken block; ``missing_block_notice_enabled``, its name
    before the suffix was shortened, still works and warns.

    *repair_enabled* has the small model write the line the listener should
    have heard, for a reply that needed a block and opened none, instead of
    reading that reply whole. It is asked once at the end of the turn, so a
    slow or missing model costs a pause rather than silence; *repair_model*
    picks the model (empty: the small model) and *repair_timeout* bounds the
    wait.

    *backend* names a built-in backend (``auto``, ``termux``, ``say``,
    ``espeak-ng``, ``openai``, ``gemini``), built from the fields here, or is
    an `AnySpeechBackend` of your own, which ignores them.

    A *volume* is a percentage of the speech's own level, 0-200, and applies
    where zrb plays the audio itself — a player program keeps its own.

    Every field is a keyword. Until 4.0 the class took them by position too, on
    the rule that a new field goes at the end — but the three settings a long
    reply's summary used sat in the middle, and retiring them moved every field
    after them up three places. A call built against 4.0.0b1 would have set
    `progress_interval` from the `600` it meant for `summarize_above_chars`, and
    `openai_base_url` from what it meant for `progress_interval`, without a
    word. A keyword-only constructor cannot be misbound at all, so a field may
    now be added or retired anywhere in this list.
    """

    enabled: bool | None = None
    commands: list[str] | None = None
    backend: "str | AnySpeechBackend | None" = None
    voice: str | None = None
    style: str | None = None
    rate: int | None = None
    volume: int | None = None
    stream: bool | None = None
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
    emotion_voices: dict[str, str] | None = None
    player_prebuffer_seconds: float | None = None
    chunk_max_chars: int | None = None
    block_notice_enabled: bool | None = None
    repair_enabled: bool | None = None
    repair_model: str | None = None
    repair_timeout: float | None = None

    def resolve(self) -> "SpeechConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_SPEECH_")
