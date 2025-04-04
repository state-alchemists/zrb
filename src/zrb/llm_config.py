import os

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers import Provider
from pydantic_ai.providers.openai import OpenAIProvider

DEFAULT_SYSTEM_PROMPT = """
You have access to tools.
Your goal is to provide insightful and accurate information based on user queries.
Follow these instructions precisely:
1. ALWAYS use available tools to gather information BEFORE asking the user questions.
2. For tools that require arguments: provide arguments in valid JSON format.
3. For tools with no args: call the tool without args. Do NOT pass "" or {}.
4. NEVER pass arguments to tools that don't accept parameters.
5. NEVER ask users for information obtainable through tools.
6. Use tools in a logical sequence until you have sufficient information.
7. If a tool call fails, check if you're passing arguments in the correct format.
   Consider alternative strategies if the issue persists.
8. Only after exhausting relevant tools should you request clarification.
9. Understand the context of user queries to provide relevant and accurate responses.
10. Engage with users in a conversational manner once the necessary information is gathered.
11. Adapt to different query types or scenarios to improve flexibility and effectiveness.
""".strip()

DEFAULT_PERSONA = """
You are an expert in various fields including technology, science, history, and more.
""".strip()


class LLMConfig:

    def __init__(
        self,
        default_model_name: str | None = None,
        default_base_url: str | None = None,
        default_api_key: str | None = None,
        default_persona: str | None = None,
        default_system_prompt: str | None = None,
    ):
        self._default_model_name = (
            default_model_name
            if default_model_name is not None
            else os.getenv("ZRB_LLM_MODEL", None)
        )
        self._default_model_base_url = (
            default_base_url
            if default_base_url is not None
            else os.getenv("ZRB_LLM_BASE_URL", None)
        )
        self._default_model_api_key = (
            default_api_key
            if default_api_key is not None
            else os.getenv("ZRB_LLM_API_KEY", None)
        )
        self._default_system_prompt = (
            default_system_prompt
            if default_system_prompt is not None
            else os.getenv("ZRB_LLM_SYSTEM_PROMPT", None)
        )
        self._default_persona = (
            default_persona
            if default_persona is not None
            else os.getenv("ZRB_LLM_PERSONA", None)
        )
        self._default_provider = None
        self._default_model = None

    def _get_model_name(self) -> str | None:
        return (
            self._default_model_name if self._default_model_name is not None else None
        )

    def get_default_model_provider(self) -> Provider | str:
        if self._default_provider is not None:
            return self._default_provider
        if self._default_model_base_url is None and self._default_model_api_key is None:
            return "openai"
        return OpenAIProvider(
            base_url=self._default_model_base_url, api_key=self._default_model_api_key
        )

    def get_default_system_prompt(self) -> str:
        system_prompt = (
            DEFAULT_SYSTEM_PROMPT
            if self._default_system_prompt is None
            else self._default_system_prompt
        )
        persona = (
            DEFAULT_PERSONA if self._default_persona is None else self._default_persona
        )
        if persona is not None:
            return f"{persona}\n{system_prompt}"
        return system_prompt

    def get_default_model(self) -> Model | str | None:
        if self._default_model is not None:
            return self._default_model
        model_name = self._get_model_name()
        if model_name is None:
            return None
        return OpenAIModel(
            model_name=model_name,
            provider=self.get_default_model_provider(),
        )

    def set_default_persona(self, persona: str):
        self._default_persona = persona

    def set_default_system_prompt(self, system_prompt: str):
        self._default_system_prompt = system_prompt

    def set_default_model_name(self, model_name: str):
        self._default_model_name = model_name

    def set_default_model_api_key(self, model_api_key: str):
        self._default_model_api_key = model_api_key

    def set_default_model_base_url(self, model_base_url: str):
        self._default_model_base_url = model_base_url

    def set_default_provider(self, provider: Provider | str):
        self._default_provider = provider

    def set_default_model(self, model: Model | str | None):
        self._default_model = model


llm_config = LLMConfig()
