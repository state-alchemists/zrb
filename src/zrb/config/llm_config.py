from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


DEFAULT_PERSONA = (
    "You are a helpful and efficient AI agent specializing in CLI "
    "interaction."
)

CORE_MANDATES = (
    "### Core Mandates\n"
    "- **Safety and Verification:** Always prioritize safety. Explain\n"
    "  potentially destructive commands before running them. After making\n"
    "  changes, verify them with tests, linters, or builds.\n"
    "- **Respect Conventions:** Strive to match the existing coding style,\n"
    "  formatting, and architecture. Use your tools to understand the\n"
    "  project's conventions before writing code.\n"
    "- **Tool-First Approach:** Don't make assumptions. Use your tools to\n"
    "  investigate the environment, dependencies, and existing code before\n"
    "  acting."
).strip()

DEFAULT_INTERACTIVE_SYSTEM_PROMPT = (
    "You are an interactive CLI agent. Your standard response format is\n"
    "GitHub-flavored Markdown. You MUST follow this workflow:\n\n"
    "1.  **Analyze Request:** Before doing anything else, you MUST analyze the\n"
    "    user's request by considering the `Scratchpad` and asking\n"
    "    yourself:\n"
    "    - **Intent & Target:** Is this a new, unrelated question or a follow-up\n"
    "      to my last response? What, specifically, is the target of the request?\n"
    "    - **Scope:** Is this a one-time instruction or a permanent\n"
    "      change? A one-time request applies ONLY to the current target\n"
    "      and MUST be forgotten for the next unrelated question.\n\n"
    "2.  **Plan:** Based on your analysis, create a concise plan.\n"
    "3.  **Confirm & Execute:** For any action that modifies or deletes files,\n"
    "    you MUST ask for user approval. For safe, read-only actions, you\n"
    "    can proceed without confirmation. Then, execute the plan."
).strip()

DEFAULT_SYSTEM_PROMPT = (
    "You are a direct command-line agent. Your final answer MUST be in\n"
    "GitHub-flavored Markdown. Before answering, you MUST analyze the user's\n"
    "request:\n"
    "- **Intent & Target:** Is this a new question or a follow-up to the\n"
    "  `Scratchpad`? What is the target?\n"
    "- **Scope:** Is this a one-time format request? If so, it does NOT apply\n"
    "  to subsequent, unrelated questions.\n\n"
    "Fulfill the request concisely after verifying any outdated information."
).strip()

DEFAULT_SUMMARIZATION_PROMPT = (
    "You are a Conversation Historian. Your task is to distill the\n"
    "conversation history into a dense, structured snapshot for the main\n"
    "assistant. This snapshot is CRITICAL, as it will become the agent's\n"
    "primary short-term memory.\n\n"
    "## Historian Protocol\n"
    "You will receive a `Previous Summary` and the `Recent Conversation\n"
    "History`. Your job is to create a new, updated summary.\n\n"
    "### 1. Update the Narrative Summary\n"
    "- **Integrate:** Weave the key events from the `Recent Conversation\n"
    "  History` into the `Narrative Summary`.\n"
    "- **Condense and Prune:** As you add new information, you MUST condense\n"
    "  older parts of the narrative. Be incredibly dense with information.\n"
    "  Omit any irrelevant conversational filler. The summary should be a\n"
    "  rolling, high-level overview, not an ever-expanding log.\n\n"
    "### 2. Update the Scratchpad\n"
    "- **Purpose:** The Scratchpad is the assistant's working memory. It must\n"
    "  contain the last few turns of the conversation in full, non-truncated\n"
    "  detail.\n"
    "- **ABSOLUTE REQUIREMENT: The assistant's response MUST be copied\n"
    "  verbatim into the Scratchpad. It is critical that you DO NOT\n"
    "  truncate, summarize, use placeholders, or alter the assistant's\n"
    "  response in any way. The entire, full response must be preserved.**\n"
    "- **Format:** Present the assistant's turn as: `assistant (thought:\n"
    "  brief summary of action) final response`.\n\n"
    "### 3. Output Specification\n"
    "Your entire output MUST be a single block of text with these two\n"
    "sections:\n"
    "1.  `## Narrative Summary` (The updated and condensed narrative)\n"
    "2.  `## Scratchpad` (The new, non-truncated recent history)"
).strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = (
    "You are a Memory Curator. Your sole purpose is to process a\n"
    "conversation and produce a concise, up-to-date Markdown block of\n"
    "long-term context for the main assistant.\n\n"
    "You will be given the previous 'Long-Term Context' and the 'Recent\n"
    "Conversation History'. Your job is to return a NEW, UPDATED version of\n"
    "the 'Long-Term Context'.\n\n"
    "**Your Curation Process:**\n"
    "1.  **Review:** Analyze the existing 'Long-Term Context'.\n"
    "2.  **Update:** Read the 'Recent Conversation History' to identify\n"
    "    new facts, changed goals, or completed tasks.\n"
    "3.  **Re-write:** Create the new 'Long-Term Context' by applying these\n"
    "    changes.\n\n"
    "**CRITICAL CURATION RULES:**\n"
    "- **The context MUST NOT grow indefinitely.** Your primary goal is to\n"
    "  keep it concise and relevant to the *current* state of the\n"
    "  conversation.\n"
    "- **ADD** new, stable facts (e.g., long-term user preferences).\n"
    "- **UPDATE** existing facts if the user provides new information.\n"
    "- **REMOVE** goals, tasks, or files that are completed or no longer\n"
    "  relevant. Be aggressive in pruning irrelevant information.\n"
    "- **CONDENSE** older entries that are still relevant but not the\n"
    "  immediate focus. For example, a completed high-level goal might be\n"
    "  condensed into a single 'Past Accomplishments' line item.\n\n"
    "**A Note on Dynamic Information:**\n"
    "Be mindful that some information is temporary. Details like the current\n"
    "working directory, project context, or file contents can change\n"
    "frequently. The main assistant MUST NOT assume this information is\n"
    "current and should always use its tools to verify the latest state when\n"
    "needed."
).strip()


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
        default_context_enrichment_prompt: str | None = None,
        default_summarize_history: bool | None = None,
        default_history_summarization_token_threshold: int | None = None,
        default_enrich_context: bool | None = None,
        default_context_enrichment_token_threshold: int | None = None,
        default_model: "Model | None" = None,
        default_model_settings: "ModelSettings | None" = None,
        default_model_provider: "Provider | None" = None,
    ):
        self._default_model_name = default_model_name
        self._default_model_base_url = default_base_url
        self._default_model_api_key = default_api_key
        self._default_persona = default_persona
        self._default_system_prompt = default_system_prompt
        self._default_interactive_system_prompt = default_interactive_system_prompt
        self._default_special_instruction_prompt = default_special_instruction_prompt
        self._default_summarization_prompt = default_summarization_prompt
        self._default_context_enrichment_prompt = default_context_enrichment_prompt
        self._default_summarize_history = default_summarize_history
        self._default_history_summarization_token_threshold = (
            default_history_summarization_token_threshold
        )
        self._default_enrich_context = default_enrich_context
        self._default_context_enrichment_token_threshold = (
            default_context_enrichment_token_threshold
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
    def default_model_settings(self) -> "ModelSettings | None":
        if self._default_model_settings is not None:
            return self._default_model_settings
        return None

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
        if self._default_system_prompt is not None:
            return self._default_system_prompt
        if CFG.LLM_SYSTEM_PROMPT is not None:
            return f"{CFG.LLM_SYSTEM_PROMPT}"
        return f"{DEFAULT_SYSTEM_PROMPT}\n{CORE_MANDATES}"

    @property
    def default_interactive_system_prompt(self) -> str:
        if self._default_interactive_system_prompt is not None:
            return self._default_interactive_system_prompt
        if CFG.LLM_INTERACTIVE_SYSTEM_PROMPT is not None:
            return f"{CFG.LLM_INTERACTIVE_SYSTEM_PROMPT}"
        return f"{DEFAULT_INTERACTIVE_SYSTEM_PROMPT}\n{CORE_MANDATES}"

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
        return ""

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
    def default_model(self) -> "Model | str | None":
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
    def default_history_summarization_token_threshold(self) -> int:
        if self._default_history_summarization_token_threshold is not None:
            return self._default_history_summarization_token_threshold
        return CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD

    @property
    def default_enrich_context(self) -> bool:
        if self._default_enrich_context is not None:
            return self._default_enrich_context
        return CFG.LLM_ENRICH_CONTEXT

    @property
    def default_context_enrichment_token_threshold(self) -> int:
        if self._default_context_enrichment_token_threshold is not None:
            return self._default_context_enrichment_token_threshold
        return CFG.LLM_CONTEXT_ENRICHMENT_TOKEN_THRESHOLD

    def set_default_persona(self, persona: str):
        self._default_persona = persona

    def set_default_system_prompt(self, system_prompt: str):
        self._default_system_prompt = system_prompt

    def set_default_interactive_system_prompt(self, interactive_system_prompt: str):
        self._default_interactive_system_prompt = interactive_system_prompt

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

    def set_default_enrich_context(self, enrich_context: bool):
        self._default_enrich_context = enrich_context

    def set_default_context_enrichment_token_threshold(
        self, context_enrichment_token_threshold: int
    ):
        self._default_context_enrichment_token_threshold = (
            context_enrichment_token_threshold
        )

    def set_default_model_settings(self, model_settings: "ModelSettings"):
        self._default_model_settings = model_settings


llm_config = LLMConfig()
