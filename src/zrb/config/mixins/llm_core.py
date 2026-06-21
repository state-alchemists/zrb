"""LLM core: model, API key, base URL, model-list visibility toggles."""

from __future__ import annotations

from zrb.config.env_field import EnvField, on_off
from zrb.util.string.conversion import to_boolean


class LLMCoreMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_MODEL: str = ""
        self.DEFAULT_LLM_SMALL_MODEL: str = ""
        self.DEFAULT_LLM_MULTIMODAL_MODEL: str = ""
        self.DEFAULT_LLM_BASE_URL: str = ""
        self.DEFAULT_LLM_API_KEY: str = ""
        self.DEFAULT_LLM_SHOW_OLLAMA_MODELS: str = "on"
        self.DEFAULT_LLM_SHOW_PYDANTIC_AI_MODELS: str = "on"
        self.DEFAULT_LLM_PERMISSIONS: str = ""
        super().__init__()

    LLM_MODEL = EnvField(
        str,
        nullable=True,
        doc="Primary LLM model identifier (e.g. openai:gpt-4o). Unset uses the provider default.",
    )

    LLM_SMALL_MODEL = EnvField(
        str,
        nullable=True,
        doc="Lightweight model for less demanding tasks. Falls back to LLM_MODEL when unset.",
    )

    LLM_MULTIMODAL_MODEL = EnvField(
        str,
        nullable=True,
        doc="Multimodal model for image/file tasks. Falls back to LLM_MODEL when unset.",
    )

    LLM_BASE_URL = EnvField(
        str,
        nullable=True,
        doc="Custom base URL for the LLM API endpoint. Unset uses the provider default.",
    )

    LLM_API_KEY = EnvField(
        str,
        nullable=True,
        doc="API key for the LLM provider. Unset defers to the provider's own env var (e.g. OPENAI_API_KEY).",
    )

    LLM_SHOW_OLLAMA_MODELS = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Enable/disable showing Ollama models in model completion.",
    )

    LLM_SHOW_PYDANTIC_AI_MODELS = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Enable/disable showing pydantic-ai KnownModelName models in model "
            "completion."
        ),
    )

    LLM_PERMISSIONS = EnvField(
        str,
        nullable=True,
        doc=(
            "Tool permission ruleset. Empty (default) keeps legacy yolo "
            "behavior. Accepts a shorthand ('allow'/'ask'/'deny') or a "
            "comma-separated 'key:action' list where key is a tool name, a "
            "capability (read/edit/execute/network/delegate/meta), or '*', "
            "e.g. 'edit:deny,Bash:ask,*:allow'. First match wins; 'deny' is "
            "enforced before the tool runs, 'allow' skips approval, 'ask' "
            "prompts."
        ),
    )
