import os
from typing import TYPE_CHECKING, Any, Callable

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


class LLMConfig:
    def __init__(
        self,
        default_model_name: str | None = None,
        default_base_url: str | None = None,
        default_api_key: str | None = None,
        default_persona: str | None = None,
        default_system_prompt: str | None = None,
        default_interactive_system_prompt: str | None = None,
        default_special_instruction_prompt: str | None = None,
        default_summarization_prompt: str | None = None,
        default_summarize_history: bool | None = None,
        default_history_summarization_token_threshold: int | None = None,
        default_modes: list[str] | None = None,
        default_model: "Model | None" = None,
        default_model_settings: "ModelSettings | None" = None,
        default_model_provider: "Provider | None" = None,
        default_yolo_mode: bool | list[str] | None = None,
    ):
        self.__internal_default_prompt: dict[str, str] = {}
        self._default_model_name = default_model_name
        self._default_model_base_url = default_base_url
        self._default_model_api_key = default_api_key
        self._default_persona = default_persona
        self._default_system_prompt = default_system_prompt
        self._default_interactive_system_prompt = default_interactive_system_prompt
        self._default_special_instruction_prompt = default_special_instruction_prompt
        self._default_summarization_prompt = default_summarization_prompt
        self._default_summarize_history = default_summarize_history
        self._default_history_summarization_token_threshold = (
            default_history_summarization_token_threshold
        )
        self._default_modes = default_modes
        self._default_model = default_model
        self._default_model_settings = default_model_settings
        self._default_model_provider = default_model_provider
        self._default_yolo_mode = default_yolo_mode

    def _get_internal_default_prompt(self, name: str) -> str:
        if name not in self.__internal_default_prompt:
            file_path = os.path.join(
                os.path.dirname(__file__), "default_prompt", f"{name}.md"
            )
            with open(file_path, "r") as f:
                self.__internal_default_prompt[name] = f.read().strip()
        return self.__internal_default_prompt[name]

    def _get_property(
        self,
        instance_var: Any,
        config_var: Any,
        default_func: Callable[[], Any],
    ) -> Any:
        if instance_var is not None:
            return instance_var
        if config_var is not None:
            return config_var
        return default_func()

    @property
    def default_model_name(self) -> str | None:
        return self._get_property(self._default_model_name, CFG.LLM_MODEL, lambda: None)

    @property
    def default_model_base_url(self) -> str | None:
        return self._get_property(
            self._default_model_base_url, CFG.LLM_BASE_URL, lambda: None
        )

    @property
    def default_model_api_key(self) -> str | None:
        return self._get_property(
            self._default_model_api_key, CFG.LLM_API_KEY, lambda: None
        )

    @property
    def default_model_settings(self) -> "ModelSettings | None":
        return self._get_property(self._default_model_settings, None, lambda: None)

    @property
    def default_model_provider(self) -> "Provider | str":
        if self._default_model_provider is not None:
            return self._default_model_provider
        if self.default_model_base_url is None and self.default_model_api_key is None:
            return "openai"
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIProvider(
            base_url=self.default_model_base_url, api_key=self.default_model_api_key
        )

    @property
    def default_system_prompt(self) -> str:
        return self._get_property(
            self._default_system_prompt,
            CFG.LLM_SYSTEM_PROMPT,
            lambda: self._get_internal_default_prompt("system_prompt"),
        )

    @property
    def default_interactive_system_prompt(self) -> str:
        return self._get_property(
            self._default_interactive_system_prompt,
            CFG.LLM_INTERACTIVE_SYSTEM_PROMPT,
            lambda: self._get_internal_default_prompt("interactive_system_prompt"),
        )

    @property
    def default_persona(self) -> str:
        return self._get_property(
            self._default_persona,
            CFG.LLM_PERSONA,
            lambda: self._get_internal_default_prompt("persona"),
        )

    @property
    def default_modes(self) -> list[str]:
        return self._get_property(
            self._default_modes, CFG.LLM_MODES, lambda: ["coding"]
        )

    @property
    def default_special_instruction_prompt(self) -> str:
        return self._get_property(
            self._default_special_instruction_prompt,
            CFG.LLM_SPECIAL_INSTRUCTION_PROMPT,
            lambda: "",
        )

    @property
    def default_summarization_prompt(self) -> str:
        return self._get_property(
            self._default_summarization_prompt,
            CFG.LLM_SUMMARIZATION_PROMPT,
            lambda: self._get_internal_default_prompt("summarization_prompt"),
        )

    @property
    def default_model(self) -> "Model | str":
        if self._default_model is not None:
            return self._default_model
        model_name = self.default_model_name
        if model_name is None:
            return "openai:gpt-4o"
        from pydantic_ai.models.openai import OpenAIChatModel

        return OpenAIChatModel(
            model_name=model_name,
            provider=self.default_model_provider,
        )

    @property
    def default_summarize_history(self) -> bool:
        return self._get_property(
            self._default_summarize_history, CFG.LLM_SUMMARIZE_HISTORY, lambda: False
        )

    @property
    def default_history_summarization_token_threshold(self) -> int:
        return self._get_property(
            self._default_history_summarization_token_threshold,
            CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD,
            lambda: 1000,
        )

    @property
    def default_yolo_mode(self) -> bool | list[str]:
        return self._get_property(
            self._default_yolo_mode, CFG.LLM_YOLO_MODE, lambda: False
        )

    def set_default_persona(self, persona: str):
        self._default_persona = persona

    def set_default_system_prompt(self, system_prompt: str):
        self._default_system_prompt = system_prompt

    def set_default_interactive_system_prompt(self, interactive_system_prompt: str):
        self._default_interactive_system_prompt = interactive_system_prompt

    def set_default_special_instruction_prompt(self, special_instruction_prompt: str):
        self._default_special_instruction_prompt = special_instruction_prompt

    def set_default_modes(self, modes: list[str]):
        self._default_modes = modes

    def add_default_mode(self, mode: str):
        if self._default_modes is None:
            self._default_modes = []
        self._default_modes.append(mode)

    def remove_default_mode(self, mode: str):
        if self._default_modes is None:
            self._default_modes = []
        self._default_modes.remove(mode)

    def set_default_summarization_prompt(self, summarization_prompt: str):
        self._default_summarization_prompt = summarization_prompt

    def set_default_model_name(self, model_name: str):
        self._default_model_name = model_name

    def set_default_model_api_key(self, model_api_key: str):
        self._default_model_api_key = model_api_key

    def set_default_model_base_url(self, model_base_url: str):
        self._default_model_base_url = model_base_url

    def set_default_model_provider(self, provider: "Provider | str"):
        self._default_model_provider = provider

    def set_default_model(self, model: "Model | str"):
        self._default_model = model

    def set_default_summarize_history(self, summarize_history: bool):
        self._default_summarize_history = summarize_history

    def set_default_history_summarization_token_threshold(
        self, history_summarization_token_threshold: int
    ):
        self._default_history_summarization_token_threshold = (
            history_summarization_token_threshold
        )

    def set_default_model_settings(self, model_settings: "ModelSettings"):
        self._default_model_settings = model_settings

    def set_default_yolo_mode(self, yolo_mode: bool | list[str]):
        self._default_yolo_mode = yolo_mode


llm_config = LLMConfig()
