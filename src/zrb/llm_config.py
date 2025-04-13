import os

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers import Provider
from pydantic_ai.providers.openai import OpenAIProvider

DEFAULT_SYSTEM_PROMPT = """
You are a highly capable AI assistant with access to tools. Your primary goal is to
provide accurate, reliable, and helpful responses.

Key Instructions:
1.  **Prioritize Tool Use:** Always attempt to use available tools to find
    information or perform actions before asking the user.
2.  **Correct Tool Invocation:** Use tools precisely as defined. Provide arguments
    in valid JSON where required. Do not pass arguments to tools that don't accept
    them. Handle tool errors gracefully and retry or adapt your strategy if necessary.
3.  **Accuracy is Paramount:** Ensure all information, code, or outputs provided are
    correct and reliable. Verify facts and generate executable code when requested.
4.  **Clarity and Conciseness:** Respond clearly and directly to the user's query
    after gathering the necessary information. Avoid unnecessary conversation.
5.  **Context Awareness:** Understand the user's request fully to provide the most
    relevant and effective assistance.
""".strip()

DEFAULT_PERSONA = """
You are an expert in various fields including technology, science, history, and more.
""".strip()

DEFAULT_SUMMARIZATION_PROMPT = """
You are a summarization assistant. Your task is to synthesize the provided 
conversation history and the existing context (which might contain a
previous 'history_summary') into a comprehensive, updated summary
Carefully review the '# Current Context' which includes any previous summary
('history_summary').
Then, review the '# Conversation History to Summarize'.
Combine the information from both the existing context/summary and the new
history. Create a single, coherent summary that captures ALL essential
information, including:
- Key decisions made
- Actions taken (including tool usage and their results)
- Important facts or data points mentioned
- Outcomes of discussions or actions
- Any unresolved questions or pending items
The goal is to provide a complete yet concise background so that the main
assistant can seamlessly continue the conversation without losing critical
context from the summarized parts.
Output *only* the updated summary text."
""".strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = """
You are an information extraction assistant.
Analyze the conversation history and current context to extract key facts such as:
  - user_name
  - user_roles
  - preferences
  - goals
  - etc
Return only a JSON object containing a single key "response",
whose value is another JSON object with these details.
If nothing is found, output {"response": {}}.
""".strip()


class LLMConfig:

    def __init__(
        self,
        default_model_name: str | None = None,
        default_base_url: str | None = None,
        default_api_key: str | None = None,
        default_persona: str | None = None,
        default_system_prompt: str | None = None,
        default_summarization_prompt: str | None = None,
        default_context_enrichment_prompt: str | None = None,
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
        self._default_summarization_prompt = (
            default_summarization_prompt
            if default_summarization_prompt is not None
            else os.getenv("ZRB_LLM_SUMMARIZATION_PROMPT", None)
        )
        self._default_context_enrichment_prompt = (
            default_context_enrichment_prompt
            if default_context_enrichment_prompt is not None
            else os.getenv("ZRB_LLM_CONTEXT_ENRICHMENT_PROMPT", None)
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

    def get_default_summarization_prompt(self) -> str:
        return (
            DEFAULT_SUMMARIZATION_PROMPT
            if self._default_summarization_prompt is None
            else self._default_summarization_prompt
        )

    def get_default_context_enrichment_prompt(self) -> str:
        return (
            DEFAULT_CONTEXT_ENRICHMENT_PROMPT
            if self._default_context_enrichment_prompt is None
            else self._default_context_enrichment_prompt
        )

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


llm_config = LLMConfig()
