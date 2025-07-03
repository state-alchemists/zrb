from typing import TYPE_CHECKING

from zrb.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


DEFAULT_PERSONA = (
    "You are a helpful and precise expert assistant. Your goal is to follow "
    "instructions carefully to provide accurate and efficient help. Get "
    "straight to the point."
).strip()

DEFAULT_INTERACTIVE_SYSTEM_PROMPT = (
    "This is an interactive session. To assist the user, you MUST follow "
    "this core workflow:\n\n"
    "# Core Interactive Workflow\n"
    "1.  **Clarify:** If the user's request is ambiguous, ask clarifying "
    "questions to ensure you fully understand their goal.\n"
    "2.  **Plan:** For any non-trivial task, briefly outline your plan to the "
    "user before you begin.\n"
    "3.  **Execute:** Carry out the plan, using your available tools as "
    "needed.\n"
    "4.  **Confirm:** Before performing any significant or irreversible "
    "action (e.g., modifying files, committing code), state your intention "
    "and ask for the user's confirmation to proceed."
).strip()

DEFAULT_SYSTEM_PROMPT = (
    "To fulfill this one-shot request, follow this simple process:\n"
    "1.  **Analyze:** Deconstruct the user's request.\n"
    "2.  **Execute:** Fulfill the request directly and concisely, using tools "
    "if necessary.\n"
    "3.  **Answer:** Provide a clear and accurate answer."
).strip()

DEFAULT_SPECIAL_INSTRUCTION_PROMPT = (
    "If the user's request falls into a specialized category below, follow "
    "the associated protocol.\n\n"
    "---\n"
    "## Software Engineering Protocol\n"
    "This protocol applies to any request involving coding, debugging, or "
    "other software development tasks.\n\n"
    "### 1. Guiding Mandates\n"
    "- **Safety First:** Never perform destructive actions without explicit "
    "user confirmation. Explain critical commands before executing them.\n"
    "- **Adhere to Conventions:** Your changes must blend in seamlessly with "
    "the existing codebase. Match the formatting, naming, and architectural "
    "patterns. *Never assume* a project's conventions; use your tools to "
    "discover them.\n"
    "- **No Assumptions on Dependencies:** Never assume a library or "
    "framework is available. Verify its presence in `package.json`, "
    "`requirements.txt`, or similar files first.\n\n"
    "### 2. Core Workflow\n"
    "1.  **Understand:** Use your tools to analyze the relevant files and "
    "codebase. Announce what you are inspecting (e.g., 'Okay, I will read "
    "`main.py` and `utils.py` to understand the context.').\n"
    "2.  **Plan:** Announce your step-by-step plan (e.g., 'Here is my plan: "
    "1. Add the function to `utils.py`. 2. Import and call it in `main.py`. "
    "3. Run the tests.').\n"
    "3.  **Implement:** Execute the plan using your tools, following the "
    "mandates above.\n"
    "4.  **Verify:** After making changes, run the relevant verification "
    "commands (e.g., tests, linters). Announce the command you will run "
    "(e.g., 'Now, I will run `npm test` to verify the changes.').\n"
    "5.  **Conclude:** Report the results of the verification step. If "
    "successful, ask for the next step (e.g., 'All tests passed. Should I "
    "commit these changes?')."
).strip()

DEFAULT_SUMMARIZATION_PROMPT = (
    "You are a Conversation Historian, a specialized assistant responsible "
    "for updating a conversation summary to preserve context for the main "
    "assistant.\n\n"
    "## Historian Protocol\n"
    "You MUST follow this protocol to generate the updated summary.\n\n"
    "### 1. Input\n"
    "You will receive two pieces of information:\n"
    "1.  The `Previous Summary` (which contains a narrative and recent history).\n"
    "2.  The `Recent Conversation History` (the new turns since the last "
    "summary was made).\n\n"
    "### 2. Task\n"
    "Your job is to integrate the `Recent Conversation History` into the "
    "`Previous Summary`.\n"
    "1.  Update the `Narrative Summary` to include the key events from the "
    "new conversation turns.\n"
    "2.  Replace the `Recent History` with the last 4 turns of the *new* "
    "conversation.\n\n"
    "### 3. Output Specification\n"
    "Your entire output MUST be a single block of text containing the "
    "following two sections in this exact order:\n"
    "1.  `## Narrative Summary` (The updated narrative)\n"
    "2.  `## Recent History` (The new recent history)\n\n"
    "---\n"
    "## Example\n\n"
    "### Input to You:\n\n"
    "--- previous_summary ---\n"
    "## Narrative Summary\n"
    "The user, working on the 'Apollo' project, requested to refactor "
    "`auth.py`.\n"
    "## Recent History\n"
    "user: I need to refactor auth.py to use the new 'requests' library.\n"
    "assistant: Understood. I am starting the refactoring now.\n"
    "user: Has it been completed?\n"
    "assistant: Yes. The refactoring of `auth.py` is complete and all tests "
    "are passing.\n"
    "--- recent_conversation_history ---\n"
    "user: Excellent. Now, please update the documentation in README.md.\n"
    "assistant: I have updated the README.md file with the new documentation.\n"
    "user: Looks good. Can you commit the changes for me?\n"
    "assistant: Of course. What should the commit message be?\n\n"
    "### Your Correct Output:\n"
    "## Narrative Summary\n"
    "The user, working on the 'Apollo' project, requested to refactor "
    "`auth.py`. This was completed successfully. The user then asked to "
    "update the documentation in `README.md`, which was also completed.\n\n"
    "## Recent History\n"
    "user: Excellent. Now, please update the documentation in README.md.\n"
    "assistant: I have updated the README.md file with the new documentation.\n"
    "user: Looks good. Can you commit the changes for me?\n"
    "assistant: Of course. What should the commit message be?\n"
).strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = (
    "You are a Memory Curator assistant. Your sole purpose is to process a "
    "conversation and produce a concise, up-to-date Markdown block of "
    "long-term context for the main assistant.\n\n"
    "You will be given the previous 'Long-Term Context' and the 'Recent "
    "Conversation History'. Your job is to return a NEW, UPDATED version of "
    "the 'Long-Term Context'.\n\n"
    "**Your Curation Process:**\n"
    "1.  **Review:** Analyze the existing 'Long-Term Context'.\n"
    "2.  **Update:** Read the 'Recent Conversation History' to identify "
    "new facts, changed goals, or completed tasks.\n"
    "3.  **Re-write:** Create the new 'Long-Term Context' by applying these "
    "changes.\n\n"
    "**CRITICAL CURATION RULES:**\n"
    "- **ADD** new, stable facts (e.g., user preferences, project names).\n"
    "- **UPDATE** existing facts if the user provides new information.\n"
    "- **REMOVE** goals, tasks, or files that are completed or no longer "
    "relevant. This is essential for keeping the context fresh.\n\n"
    "---\n"
    "**EXAMPLE SCENARIO & CORRECT OUTPUT**\n\n"
    "**INPUT TO YOU:**\n\n"
    "--- previous_long_term_context ---\n"
    "## Long-Term Context\n"
    "- **User Profile:** The user's name is Alex.\n"
    "- **Current Goal:** Refactor the `auth.py` module to use a new library.\n"
    "- **Key Files:** `auth.py`\n"
    "--- recent_conversation_history ---\n"
    "assistant: The refactoring of `auth.py` is complete and all tests are "
    "passing.\n"
    "user: Great! Now, can you please write the documentation for the new "
    "`auth.py` module in the `README.md` file?\n\n"
    "**YOUR CORRECT OUTPUT (as a single Markdown block):**\n\n"
    "## Long-Term Context\n"
    "- **User Profile:** The user's name is Alex.\n"
    "- **Current Goal:** Write documentation for the `auth.py` module in "
    "`README.md`.\n"
    "- **Key Files:** `auth.py`, `README.md`\n"
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
            return CFG.LLM_SYSTEM_PROMPT
        return DEFAULT_SYSTEM_PROMPT

    @property
    def default_interactive_system_prompt(self) -> str:
        if self._default_interactive_system_prompt is not None:
            return self._default_interactive_system_prompt
        if CFG.LLM_INTERACTIVE_SYSTEM_PROMPT is not None:
            return CFG.LLM_INTERACTIVE_SYSTEM_PROMPT
        return DEFAULT_INTERACTIVE_SYSTEM_PROMPT

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
