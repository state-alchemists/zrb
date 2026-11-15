"""Preset defaults for speech, dictation mode, barge-in and echo cancellation."""

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
        "LLM_DICTATION_ECHO_CANCEL_ENABLED": "on",
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
            "{ENV_PREFIX}_LLM_SPEECH_ENABLED, {ENV_PREFIX}_LLM_DICTATION_MODE, "
            "{ENV_PREFIX}_LLM_DICTATION_BARGE_IN_ENABLED and "
            "{ENV_PREFIX}_LLM_DICTATION_ECHO_CANCEL_ENABLED together (each "
            "still wins when set on its own). One of:\n"
            "- 'off' (default): typing; /speech and /voice switch voice on.\n"
            "- 'speak': replies are read aloud.\n"
            "- 'turns': read aloud and always listening; you and the assistant take "
            "turns.\n"
            "- 'conversation': as 'turns', and you can talk over the assistant to "
            "interrupt it; on macOS, the assistant's voice is cancelled out of the "
            "microphone."
        ),
    )

    LLM_VOICE_REMOTE_URL = EnvField(
        str,
        doc=(
            "Base URL of the face server whose page carries your voice, such as "
            "http://127.0.0.1:7777. Set, this one setting moves both halves: "
            "dictation reads the microphone from that server's GET /audio/in, "
            "and every sentence speech says goes to its POST /say, so this "
            "machine opens neither a microphone nor an output stream, and the "
            "voice is only where the page is — a phone held across the room, "
            "say. It decides over {ENV_PREFIX}_LLM_SPEECH_PLAYER: nothing here "
            "hands a sentence to a player program on this machine, which would "
            "speak it a second time, and a server that cannot be reached says "
            "so instead of falling back. Echo cancellation is the browser's "
            "(getUserMedia), so "
            "{ENV_PREFIX}_LLM_DICTATION_ECHO_CANCEL_ENABLED is not used while "
            "this is set. Empty (default) leaves the microphone and the "
            "speaker exactly where they were, on this machine."
        ),
    )

    LLM_VOICE_REMOTE_TOKEN = EnvField(
        str,
        aliases=["LLM_VOICE_REMOTE_TOKEN", "AVATAR_TOKEN"],
        secret=True,
        doc=(
            "Token sent to the face server as `Authorization: Bearer <token>`, "
            "which it wants on every route once its own "
            "{ENV_PREFIX}_AVATAR_TOKEN is set. Unset here, "
            "{ENV_PREFIX}_AVATAR_TOKEN is read instead, so one token names both "
            "sides of the pair. Unset in both (default): no `Authorization` "
            "header is sent, which is how a server without a token answers."
        ),
    )
