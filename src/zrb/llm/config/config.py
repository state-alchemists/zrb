from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


class LLMConfig:
    """
    Configuration provider for Pollux.
    Allows runtime configuration while falling back to ZRB global settings.
    """

    def __init__(self):
        self._model: "str | Model | None" = None
        self._model_settings: "ModelSettings | None" = None
        self._system_prompt: str | None = None
        self._summarization_prompt: str | None = None

        # Optional overrides for provider resolution
        self._api_key: str | None = None
        self._base_url: str | None = None
        self._provider: "str | Provider | None" = None

    # --- Model ---

    @property
    def model(self) -> "str | Model":
        """
        The LLM model to use. Returns a model string (e.g. 'openai:gpt-4o')
        or a pydantic_ai Model object.
        """
        if self._model is not None:
            return self._model

        model_name = CFG.LLM_MODEL or "openai:gpt-4o"
        provider = self.provider

        return self._resolve_model(model_name, provider)

    @model.setter
    def model(self, value: "str | Model"):
        self._model = value

    # --- Model Settings ---

    @property
    def model_settings(self) -> "ModelSettings | None":
        """Runtime settings for the model (temperature, etc.)."""
        return self._model_settings

    @model_settings.setter
    def model_settings(self, value: "ModelSettings"):
        self._model_settings = value

    # --- Provider Helpers (Advanced) ---

    @property
    def api_key(self) -> str | None:
        return self._api_key or getattr(CFG, "LLM_API_KEY", None)

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value

    @property
    def base_url(self) -> str | None:
        return self._base_url or getattr(CFG, "LLM_BASE_URL", None)

    @base_url.setter
    def base_url(self, value: str):
        self._base_url = value

    @property
    def provider(self) -> "str | Provider":
        """Resolves the model provider based on config."""
        if self._provider is not None:
            return self._provider

        # If API Key or Base URL is set, we assume OpenAI-compatible provider
        if self.api_key or self.base_url:
            from pydantic_ai.providers.openai import OpenAIProvider

            return OpenAIProvider(api_key=self.api_key, base_url=self.base_url)

        return "openai"

    @provider.setter
    def provider(self, value: "str | Provider"):
        self._provider = value

    # --- Internal Logic ---

    def _resolve_model(
        self, model_name: str, provider: "str | Provider"
    ) -> "str | Model":
        # Strip existing provider prefix if present
        clean_model_name = model_name.split(":", 1)[-1]

        # 1. Provider is an Object (e.g. OpenAIProvider created from custom config)
        # We check specific types we know how to wrap
        try:
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            if isinstance(provider, OpenAIProvider):
                return OpenAIChatModel(model_name=clean_model_name, provider=provider)
        except ImportError:
            pass

        # 2. Provider is a String
        if isinstance(provider, str):
            return f"{provider}:{clean_model_name}"

        # 3. Fallback (Provider is None or unknown object)
        return model_name


llm_config = LLMConfig()
