"""LLM core: model, API key, base URL, model-list visibility toggles."""

from __future__ import annotations

import os

from zrb.config.helper import get_env
from zrb.util.string.conversion import to_boolean


class LLMCoreMixin:
    def __init__(self):
        self.DEFAULT_LLM_MODEL: str = ""
        self.DEFAULT_LLM_SMALL_MODEL: str = ""
        self.DEFAULT_LLM_BASE_URL: str = ""
        self.DEFAULT_LLM_API_KEY: str = ""
        self.DEFAULT_LLM_SHOW_OLLAMA_MODELS: str = "on"
        self.DEFAULT_LLM_SHOW_PYDANTIC_AI_MODELS: str = "on"
        super().__init__()

    @property
    def LLM_MODEL(self) -> str | None:
        value = get_env("LLM_MODEL", self.DEFAULT_LLM_MODEL, self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_MODEL.setter
    def LLM_MODEL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_MODEL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_MODEL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_MODEL"] = value

    @property
    def LLM_SMALL_MODEL(self) -> str | None:
        value = get_env(
            "LLM_SMALL_MODEL", self.DEFAULT_LLM_SMALL_MODEL, self.ENV_PREFIX
        )
        return None if value == "" else value

    @LLM_SMALL_MODEL.setter
    def LLM_SMALL_MODEL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_SMALL_MODEL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_SMALL_MODEL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_SMALL_MODEL"] = value

    @property
    def LLM_BASE_URL(self) -> str | None:
        value = get_env("LLM_BASE_URL", self.DEFAULT_LLM_BASE_URL, self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_BASE_URL.setter
    def LLM_BASE_URL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_BASE_URL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_BASE_URL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_BASE_URL"] = value

    @property
    def LLM_API_KEY(self) -> str | None:
        value = get_env("LLM_API_KEY", self.DEFAULT_LLM_API_KEY, self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_API_KEY.setter
    def LLM_API_KEY(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_API_KEY" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_API_KEY"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_API_KEY"] = value

    @property
    def LLM_SHOW_OLLAMA_MODELS(self) -> bool:
        """Enable/disable showing Ollama models in model completion."""
        return to_boolean(
            get_env(
                "LLM_SHOW_OLLAMA_MODELS",
                self.DEFAULT_LLM_SHOW_OLLAMA_MODELS,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHOW_OLLAMA_MODELS.setter
    def LLM_SHOW_OLLAMA_MODELS(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHOW_OLLAMA_MODELS"] = (
            "on" if value else "off"
        )

    @property
    def LLM_SHOW_PYDANTIC_AI_MODELS(self) -> bool:
        """Enable/disable showing pydantic-ai KnownModelName models in model completion."""
        return to_boolean(
            get_env(
                "LLM_SHOW_PYDANTIC_AI_MODELS",
                self.DEFAULT_LLM_SHOW_PYDANTIC_AI_MODELS,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHOW_PYDANTIC_AI_MODELS.setter
    def LLM_SHOW_PYDANTIC_AI_MODELS(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHOW_PYDANTIC_AI_MODELS"] = (
            "on" if value else "off"
        )
