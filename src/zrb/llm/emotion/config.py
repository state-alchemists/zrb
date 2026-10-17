from __future__ import annotations

from dataclasses import dataclass

from zrb.llm.util.feature_config import resolve_from_cfg


@dataclass
class EmotionConfig:
    """Settings for `enable_emotion`. Each field mirrors
    `CFG.LLM_EMOTION_<FIELD>`; one left ``None`` is read from there when a
    session starts.

    New fields go at the end: a caller may pass them positionally, and a field
    inserted earlier would shift every argument after it.
    """

    enabled: bool | None = None

    def resolve(self) -> "EmotionConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_EMOTION_")
