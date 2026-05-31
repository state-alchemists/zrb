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
        super().__init__()

    LLM_MODEL = EnvField(str, nullable=True)

    LLM_SMALL_MODEL = EnvField(str, nullable=True)

    LLM_MULTIMODAL_MODEL = EnvField(str, nullable=True)

    LLM_BASE_URL = EnvField(str, nullable=True)

    LLM_API_KEY = EnvField(str, nullable=True)

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
