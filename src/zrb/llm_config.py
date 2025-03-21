import os

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


class LLMConfig:

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self._model_name = (
            model_name if model_name is not None else os.getenv("ZRB_LLM_MODEL", None)
        )
        self._base_url = (
            base_url if base_url is not None else os.getenv("ZRB_LLM_BASE_URL", None)
        )
        self._api_key = (
            api_key if api_key is not None else os.getenv("ZRB_LLM_API_KEY", None)
        )
        self._default_model = None

    def _get_model_name(self) -> str | None:
        return self._model_name if self._model_name is not None else None

    def _get_model_provider(self) -> OpenAIProvider:
        if self._base_url is None and self._api_key is None:
            return "openai"
        return OpenAIProvider(base_url=self._base_url, api_key=self._api_key)

    def get_default_model(self) -> Model | str | None:
        if self._default_model is not None:
            return self._default_model
        model_name = self._get_model_name()
        if model_name is None:
            return None
        return OpenAIModel(
            model_name=model_name,
            provider=self._get_model_provider(),
        )

    def set_default_model(self, model: Model | str | None):
        self._default_model = model


llm_config = LLMConfig()
