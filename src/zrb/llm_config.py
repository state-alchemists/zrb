from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings
else:
    Model = Any
    ModelSettings = Any
    Provider = Any

from zrb.config import CFG

DEFAULT_SYSTEM_PROMPT = """
You have access to tools and two forms of memory: a narrative summary of the long-term conversation and a structured JSON object with key facts.
Your goal is to complete the user's task efficiently by synthesizing information from both memory types and the current turn.
Analyze the request and use the available tools proactively to achieve the goal.
Infer parameters and actions from the context.
Do not ask for confirmation unless strictly necessary for irreversible actions or due to critical ambiguity.
Apply relevant domain knowledge and best practices.
Respond directly and concisely upon task completion or when clarification is essential.
Make sure to always include all necessary information in your final answer.
Remember that your narrative summary may be condensed; rely on the structured JSON for precise facts when available.
""".strip()

DEFAULT_PERSONA = """
You are a helpful, clear, and precise expert in various fields including technology, science, history, and more.
As an expert, your goal is to provide accurate information efficiently, getting straight to the point while remaining helpful.
While you are an expert, if you are uncertain about a fact, state what you know and what you are unsure about.
""".strip()

# Concise summarization focused on preserving critical context for continuity.
DEFAULT_SUMMARIZATION_PROMPT = """
You are a summarization assistant. Your goal is to help the main assistant continue a conversation by creating an updated, concise summary.
You will integrate the previous summary (if any) with the new conversation history.

It is CRITICAL to preserve the immediate context of the most recent exchange. Your summary MUST conclude with the user's last intent and the assistant's pending action.
For example, if the user says "Yes" after the assistant asks "Do you want me to search?", the summary must explicitly state: "The user has confirmed that they want the assistant to proceed with the search for [topic]."

Preserve ALL critical context:
- The user's main, overarching goal.
- The user's most recent, immediate intent.
- Key decisions, facts, and entities (names, files, IDs).
- Results from any tool usage.
- Any pending questions or actions the assistant was about to take.

Do not omit details that would force the main assistant to re-ask a question the user has already answered.
Output *only* the updated summary text.
""".strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = """
You are an information extraction assistant. Your goal is to help the main assistant by extracting important structured information from the conversation.
Handle all data, especially personally identifiable information (PII), with strict confidentiality.

Analyze the conversation to extract two types of information:
1. **Stable Facts**: Key-value pairs that are unlikely to change often (e.g., user_name, user_id, project_name).
2. **Conversational State**: The immediate task-related context. This is critical for maintaining continuity.
   - "user_intent": The user's most recently stated goal (e.g., "find information about Albert Einstein").
   - "pending_action": An action the assistant has proposed and is awaiting confirmation for or is about to execute (e.g., "search_internet").
   - "action_parameters": A JSON object of parameters for the pending_action (e.g., {"query": "Albert Einstein"}).

If an existing key needs to be updated (e.g., user changes their mind), replace the old value with the new one.
Return only a JSON object containing a single key "response", whose value is another JSON object with these details (i.e., {"response": {"context_name": "value"}}).
If no context can be extracted, return {"response": {}}.
""".strip()

DEFAULT_SPECIAL_INSTRUCTION_PROMPT = """
# Coding and Code Review
When asked to do coding/code review related task, you prioritize correctness, readability,
performance, security, and maintainability.
Follow these principles:
1. **Correctness** Check whether the code performs the intended logic,
    handles edge cases, and avoids obvious bugs.
2. **Readability** Evaluate naming conventions, code structure, and clarity.
    Suggest improvements where code could be more understandable.
3. **Performance** Identify inefficient patterns or unnecessary operations.
    Recommend optimizations only when they provide meaningful benefit.
4. **Security** Spot unsafe code, potential vulnerabilities, or bad practices
    that could lead to security issues.
5. **Consistency** Ensure the code adheres to common language idioms,
    style guides, and project conventions.

## Code Review
When asked to do code review, you provide clear, concise, and actionable feedback.
Use inline code examples when helpful. Do not restate the code unnecessarily.
Focus on meaningful insights that help the user improve the code quality.
Avoid excessive nitpicking unless requested.
""".strip()


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
        default_model: Model | None = None,
        default_model_settings: ModelSettings | None = None,
        default_model_provider: Provider | None = None,
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
        self._default_model_settings = default_model_settings
        self._default_model_provider = default_model_provider
        self._default_model = default_model

    @property
    def default_model_name(self) -> str | None:
        if self._default_model_name is not None:
            return self._default_model_name
        if CFG.LLM_MODEL is not None:
            return CFG.LLM_MODEL
        return None

    @property
    def default_model_base_url(self) -> str | None:
        if self._default_model_base_url is not None:
            return self._default_model_base_url
        if CFG.LLM_BASE_URL is not None:
            return CFG.LLM_BASE_URL
        return None

    @property
    def default_model_api_key(self) -> str | None:
        if self._default_model_api_key is not None:
            return self._default_model_api_key
        if CFG.LLM_API_KEY is not None:
            return CFG.LLM_API_KEY

    @property
    def default_model_settings(self) -> ModelSettings | None:
        if self._default_model_settings is not None:
            return self._default_model_settings
        return None

    @property
    def default_model_provider(self) -> Provider | str:
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
        if self._default_system_prompt is not None:
            return self._default_system_prompt
        if CFG.LLM_SYSTEM_PROMPT is not None:
            return CFG.LLM_SYSTEM_PROMPT
        return DEFAULT_SYSTEM_PROMPT

    @property
    def default_persona(self) -> str:
        if self._default_persona is not None:
            return self._default_persona
        if CFG.LLM_PERSONA is not None:
            return CFG.LLM_PERSONA
        return DEFAULT_PERSONA

    @property
    def default_special_instruction_prompt(self) -> str:
        if self._default_special_instruction_prompt is not None:
            return self._default_special_instruction_prompt
        if CFG.LLM_SPECIAL_INSTRUCTION_PROMPT is not None:
            return CFG.LLM_SPECIAL_INSTRUCTION_PROMPT
        return DEFAULT_SPECIAL_INSTRUCTION_PROMPT

    @property
    def default_summarization_prompt(self) -> str:
        if self._default_summarization_prompt is not None:
            return self._default_summarization_prompt
        if CFG.LLM_SUMMARIZATION_PROMPT is not None:
            return CFG.LLM_SUMMARIZATION_PROMPT
        return DEFAULT_SUMMARIZATION_PROMPT

    @property
    def default_context_enrichment_prompt(self) -> str:
        if self._default_context_enrichment_prompt is not None:
            return self._default_context_enrichment_prompt
        if CFG.LLM_CONTEXT_ENRICHMENT_PROMPT is not None:
            return CFG.LLM_CONTEXT_ENRICHMENT_PROMPT
        return DEFAULT_CONTEXT_ENRICHMENT_PROMPT

    @property
    def default_model(self) -> Model | str | None:
        if self._default_model is not None:
            return self._default_model
        model_name = self.default_model_name
        if model_name is None:
            return None
        from pydantic_ai.models.openai import OpenAIModel

        return OpenAIModel(
            model_name=model_name,
            provider=self.default_model_provider,
        )

    @property
    def default_summarize_history(self) -> bool:
        if self._default_summarize_history is not None:
            return self._default_summarize_history
        return CFG.LLM_SUMMARIZE_HISTORY

    @property
    def default_history_summarization_threshold(self) -> int:
        if self._default_history_summarization_threshold is not None:
            return self._default_history_summarization_threshold
        return CFG.LLM_HISTORY_SUMMARIZATION_THRESHOLD

    @property
    def default_enrich_context(self) -> bool:
        if self._default_enrich_context is not None:
            return self._default_enrich_context
        return CFG.LLM_ENRICH_CONTEXT

    @property
    def default_context_enrichment_threshold(self) -> int:
        if self._default_context_enrichment_threshold is not None:
            return self._default_context_enrichment_threshold
        return CFG.LLM_CONTEXT_ENRICHMENT_THRESHOLD

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

    def set_default_model_provider(self, provider: Provider | str):
        self._default_model_provider = provider

    def set_default_model(self, model: Model | str):
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

    def set_default_model_settings(self, model_settings: ModelSettings):
        self._default_model_settings = model_settings


llm_config = LLMConfig()
