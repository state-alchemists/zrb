"""Voice preset: one setting for the usual ways of talking with zrb.

Speech and dictation have about eighty settings between them, and three of
them decide how a session feels: whether replies are read aloud
(`LLM_SPEECH_ENABLED`), whether the microphone stays open
(`LLM_DICTATION_MODE`), and whether you may talk over zrb
(`LLM_DICTATION_BARGE_IN_ENABLED`). `LLM_VOICE` sets those three together.
It only moves their defaults: any of the three set on its own still wins, so
a preset never overrides a choice the user made.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField

# Each preset's value for the settings it decides, in their env form.
VOICE_PRESETS: dict[str, dict[str, str]] = {
    "off": {},
    "speak": {"LLM_SPEECH_ENABLED": "on"},
    "turns": {"LLM_SPEECH_ENABLED": "on", "LLM_DICTATION_MODE": "hands_free"},
    "conversation": {
        "LLM_SPEECH_ENABLED": "on",
        "LLM_DICTATION_MODE": "hands_free",
        "LLM_DICTATION_BARGE_IN_ENABLED": "on",
    },
}


def to_voice_preset(raw: str) -> str:
    preset = raw.strip().lower().replace("-", "_")
    if preset not in VOICE_PRESETS:
        raise ValueError(
            f"unknown voice preset {raw!r}; use one of: {', '.join(VOICE_PRESETS)}"
        )
    return preset


def get_voice_default(config: object, name: str) -> str:
    """*name*'s default under *config*'s voice preset, else its
    `DEFAULT_<name>`."""
    preset = VOICE_PRESETS[getattr(config, "LLM_VOICE")]
    if name in preset:
        return preset[name]
    return getattr(config, f"DEFAULT_{name}")


class LLMVoiceMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_VOICE: str = "off"
        super().__init__()

    LLM_VOICE = EnvField(
        to_voice_preset,
        doc=(
            "How a session talks with you, setting the defaults of "
            "{ENV_PREFIX}_LLM_SPEECH_ENABLED, {ENV_PREFIX}_LLM_DICTATION_MODE "
            "and {ENV_PREFIX}_LLM_DICTATION_BARGE_IN_ENABLED together (each "
            "still wins when set on its own). One of:\n"
            "- 'off' (default): typing; /speech and /voice switch voice on.\n"
            "- 'speak': replies are read aloud.\n"
            "- 'turns': read aloud and always listening; you and zrb take "
            "turns.\n"
            "- 'conversation': as 'turns', and you can talk over zrb to "
            "interrupt it."
        ),
    )
