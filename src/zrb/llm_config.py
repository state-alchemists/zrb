from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
else:
    Model = Any
    Provider = Any

from zrb.config import CFG

DEFAULT_SYSTEM_PROMPT = """
You have access to tools.
Your goal is to complete the user's task efficiently.
Analyze the request and use the available tools proactively to achieve the goal.
Infer parameters and actions from the context.
Do not ask for confirmation unless strictly necessary due to ambiguity or
missing critical information.
Apply relevant domain knowledge and best practices.
Respond directly and concisely upon task completion or when clarification is essential.
""".strip()

DEFAULT_PERSONA = """
You are an expert in various fields including technology, science, history, and more.
""".strip()

# Concise summarization focused on preserving critical context for continuity.
DEFAULT_SUMMARIZATION_PROMPT = """
You are a summarization assistant.
Your goal is to help main assistant to continue the conversation by creating an updated,
concise summary integrating the previous summary (if any) with the new conversation history.
Preserve ALL critical context needed for the main assistant
to continue the task effectively. This includes key facts, decisions, tool usage
results, and essential background. Do not omit details that would force the main
assistant to re-gather information.
Output *only* the updated summary text.
""".strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = """
You are an information extraction assistant.
Your goal is to help main assistant to continue the conversation by extracting
important informations.
Analyze the conversation history and current context to extract key facts like
user_name, user_roles, preferences, goals, etc.
Return only a JSON object containing a single key "response", whose value is
another JSON object with these details (i.e., {"response": {"context_name": "value"}}).
If no context can be extracted, return {"response": {}}.
""".strip()

DEFAULT_SPECIAL_INSTRUCTION_PROMPT = ""  # Default to empty


class LLMConfig:

    def __init__(
        self,
        default_model_name: str | None = None,
        default_base_url: str | None = None,
        default_api_key: str | None = None,
        default_persona: str | None = None,
        default_system_prompt: str | None = None,
        default_special_instruction_prompt: str | None = None,
        default_summarization_prompt: str | None = None,
        default_context_enrichment_prompt: str | None = None,
        default_summarize_history: bool | None = None,
        default_history_summarization_threshold: int | None = None,
        default_enrich_context: bool | None = None,
        default_context_enrichment_threshold: int | None = None,
    ):
        self._default_model_name = default_model_name
        self._default_model_base_url = default_base_url
        self._default_model_api_key = default_api_key
        self._default_persona = default_persona
        self._default_system_prompt = default_system_prompt
        self._default_special_instruction_prompt = default_special_instruction_prompt
        self._default_summarization_prompt = default_summarization_prompt
        self._default_context_enrichment_prompt = default_context_enrichment_prompt
        self._default_summarize_history = default_summarize_history
        self._default_history_summarization_threshold = (
            default_history_summarization_threshold
        )
        self._default_enrich_context = default_enrich_context
        self._default_context_enrichment_threshold = (
            default_context_enrichment_threshold
        )
        self._default_provider = None
        self._default_model = None

    def _get_model_name(self) -> str | None:
        return (
            self._default_model_name
            if self._default_model_name is not None
            else CFG.LLM_MODEL
        )

    def get_default_model_provider(self) -> Provider | str:
        if self._default_provider is not None:
            return self._default_provider
        if self._default_model_base_url is None and self._default_model_api_key is None:
            return "openai"
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIProvider(
            base_url=self._default_model_base_url, api_key=self._default_model_api_key
        )

    def get_default_system_prompt(self) -> str:
        return (
            self._default_system_prompt
            if self._default_system_prompt is not None
            else (
                CFG.LLM_SYSTEM_PROMPT
                if CFG.LLM_SYSTEM_PROMPT is not None
                else DEFAULT_SYSTEM_PROMPT
            )
        )

    def get_default_persona(self) -> str:
        return (
            self._default_persona
            if self._default_persona is not None
            else (CFG.LLM_PERSONA if CFG.LLM_PERSONA is not None else DEFAULT_PERSONA)
        )

    def get_default_special_instruction_prompt(self) -> str:
        return (
            self._default_special_instruction_prompt
            if self._default_special_instruction_prompt is not None
            else (
                CFG.LLM_SPECIAL_INSTRUCTION_PROMPT
                if CFG.LLM_SPECIAL_INSTRUCTION_PROMPT is not None
                else DEFAULT_SPECIAL_INSTRUCTION_PROMPT
            )
        )

    def get_default_summarization_prompt(self) -> str:
        return (
            self._default_summarization_prompt
            if self._default_summarization_prompt is not None
            else (
                CFG.LLM_SUMMARIZATION_PROMPT
                if CFG.LLM_SUMMARIZATION_PROMPT is not None
                else DEFAULT_SUMMARIZATION_PROMPT
            )
        )

    def get_default_context_enrichment_prompt(self) -> str:
        return (
            self._default_context_enrichment_prompt
            if self._default_context_enrichment_prompt is not None
            else (
                CFG.LLM_CONTEXT_ENRICHMENT_PROMPT
                if CFG.LLM_CONTEXT_ENRICHMENT_PROMPT is not None
                else DEFAULT_CONTEXT_ENRICHMENT_PROMPT
            )
        )

    def get_default_model(self) -> Model | str | None:
        if self._default_model is not None:
            return self._default_model
        model_name = self._get_model_name()
        if model_name is None:
            return None
        from pydantic_ai.models.openai import OpenAIModel

        return OpenAIModel(
            model_name=model_name,
            provider=self.get_default_model_provider(),
        )

    def get_default_summarize_history(self) -> bool:
        return (
            self._default_summarize_history
            if self._default_summarize_history is not None
            else CFG.LLM_SUMMARIZE_HISTORY
        )

    def get_default_history_summarization_threshold(self) -> int:
        return (
            self._default_history_summarization_threshold
            if self._default_history_summarization_threshold is not None
            else CFG.LLM_HISTORY_SUMMARIZATION_THRESHOLD
        )

    def get_default_enrich_context(self) -> bool:
        return (
            self._default_enrich_context
            if self._default_enrich_context is not None
            else CFG.LLM_ENRICH_CONTEXT
        )

    def get_default_context_enrichment_threshold(self) -> int:
        return (
            self._default_context_enrichment_threshold
            if self._default_context_enrichment_threshold is not None
            else CFG.LLM_CONTEXT_ENRICHMENT_THRESHOLD
        )

    def set_default_persona(self, persona: str):
        self._default_persona = persona

    def set_default_system_prompt(self, system_prompt: str):
        self._default_system_prompt = system_prompt

    def set_default_special_instruction_prompt(self, special_instruction_prompt: str):
        self._default_special_instruction_prompt = special_instruction_prompt

    def set_default_summarization_prompt(self, summarization_prompt: str):
        self._default_summarization_prompt = summarization_prompt

    def set_default_context_enrichment_prompt(self, context_enrichment_prompt: str):
        self._default_context_enrichment_prompt = context_enrichment_prompt

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

    def set_default_summarize_history(self, summarize_history: bool):
        self._default_summarize_history = summarize_history

    def set_default_history_summarization_threshold(
        self, history_summarization_threshold: int
    ):
        self._default_history_summarization_threshold = history_summarization_threshold

    def set_default_enrich_context(self, enrich_context: bool):
        self._default_enrich_context = enrich_context

    def set_default_context_enrichment_threshold(
        self, context_enrichment_threshold: int
    ):
        self._default_context_enrichment_threshold = context_enrichment_threshold


llm_config = LLMConfig()
