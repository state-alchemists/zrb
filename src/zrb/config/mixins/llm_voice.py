"""Voice dictation config mixin.

Opt-in feature gated by `LLM_VOICE_ENABLED`. When enabled, the `/voice` command
toggles push-to-talk mode in the chat TUI. Heavy audio dependencies
(sounddevice, numpy) or LLM agent stack are lazy-imported — they are only loaded
when voice mode is actually activated, not at startup.

The default backend is ``vosk`` (offline, cross-platform). Other options:
``openai`` (Whisper API, model configurable via ``LLM_VOICE_OPENAI_MODEL``),
``google`` (Gemini STT, model configurable via ``LLM_VOICE_GOOGLE_MODEL``),
``multimodal`` (uses ``LLM_MULTIMODAL_MODEL`` — slower and more expensive than
dedicated STT backends).
"""

from __future__ import annotations

from zrb.config.env_field import EnvField, on_off
from zrb.util.string.conversion import to_boolean


class LLMVoiceMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_VOICE_ENABLED: str = "false"
        self.DEFAULT_LLM_VOICE_MODE: str = "vosk"
        self.DEFAULT_LLM_VOICE_PUSH_TO_TALK_KEY: str = "space"
        self.DEFAULT_LLM_VOICE_OPENAI_MODEL: str = "whisper-1"
        self.DEFAULT_LLM_VOICE_GOOGLE_MODEL: str = "gemini-2.5-flash"
        self.DEFAULT_LLM_VOICE_VOSK_MODEL_NAME: str = "vosk-model-small-en-us-0.15"
        self.DEFAULT_LLM_VOICE_VOSK_MODEL_URL: str = (
            "https://alphacephei.com/vosk/models"
        )
        super().__init__()

    LLM_VOICE_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        default="false",
        doc=(
            "Enable voice dictation in the chat TUI. When true, the /voice "
            "command toggles push-to-talk mode. Requires sounddevice + an STT "
            "backend (multimodal LLM, Whisper API, or vosk). Default: false."
        ),
    )

    LLM_VOICE_MODE = EnvField(
        str,
        doc=(
            "Speech-to-text backend for voice dictation. One of: vosk "
            "(offline, cross-platform), openai (OpenAI Whisper API), google "
            "(Google Gemini STT), multimodal (uses {ENV_PREFIX}_LLM_MULTIMODAL_MODEL, "
            "slower/ more expensive). Default: vosk."
        ),
    )

    LLM_VOICE_PUSH_TO_TALK_KEY = EnvField(
        str,
        doc=(
            "Key for push-to-talk recording when voice mode is active. "
            "prompt_toolkit key name (e.g. 'space', 'c-t' for Ctrl+T). "
            "Default: space."
        ),
    )

    LLM_VOICE_OPENAI_MODEL = EnvField(
        str,
        doc=(
            "Model name for the OpenAI Whisper API backend. "
            "Only used when LLM_VOICE_MODE=openai. "
            "Default: whisper-1."
        ),
    )

    LLM_VOICE_GOOGLE_MODEL = EnvField(
        str,
        doc=(
            "Model name for the Google Gemini STT backend. "
            "Only used when LLM_VOICE_MODE=google. "
            "Default: gemini-2.5-flash."
        ),
    )

    LLM_VOICE_VOSK_MODEL_NAME = EnvField(
        str,
        doc=(
            "Vosk model directory name (without .zip). "
            "Only used when LLM_VOICE_MODE=vosk. "
            "Default: vosk-model-small-en-us-0.15."
        ),
    )

    LLM_VOICE_VOSK_MODEL_URL = EnvField(
        str,
        doc=(
            "Base URL for downloading the Vosk model zip. "
            "The zip at <url>/<model_name>.zip is downloaded and extracted "
            "to ~/.cache/vosk/. "
            "Only used when LLM_VOICE_MODE=vosk. "
            "Default: https://alphacephei.com/vosk/models."
        ),
    )
