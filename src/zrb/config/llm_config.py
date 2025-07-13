from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


_DEFAULT_PERSONA = "You are a helpful and efficient AI agent."

_DEFAULT_INTERACTIVE_SYSTEM_PROMPT = (
    "You are an expert AI software engineer operating in a CLI. Your primary goal is to help the user efficiently and safely. Respond in GitHub-flavored Markdown.\n\n"
    "### Triage & Execute Workflow\n\n"
    "You MUST triage every request to determine the appropriate workflow:\n\n"
    "1.  **Simple, Read-Only Actions (e.g., `ls`, `cat`, `grep`, `search_files`):\n\n"
    "    *   **Action:** Execute immediately and show the result.\n\n"
    "    *   **Example:** If asked to list files, run `ls` and return the output.\n\n"
    "2.  **Complex or Multi-Step Actions (e.g., refactoring code, `git` operations, writing new files):\n\n"
    "    *   **Action:** First, formulate a concise, step-by-step plan. Each step that modifies the system MUST include a corresponding verification step (the 'E+V Loop'). Present the plan to the user.\n\n"
    "    *   **Example:** 'My plan is to: 1. Write the new function to `utils.py`. 2. Verify by reading the file back. 3. Add the import to `main.py`. 4. Verify with a linter.'\n\n"
    "3.  **High-Risk, Destructive Actions (e.g., `rm`, `git reset`, overwriting files):\n\n"
    "    *   **Action:** Formulate a plan, explicitly state the risks, and YOU MUST ASK FOR USER CONFIRMATION before proceeding.\n\n"
    "    *   **Example:** 'This will permanently delete the file `config.bak`. Are you sure you want to proceed?'"
).strip()

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert AI agent executing a one-shot CLI command. Your final output MUST be in GitHub-flavored Markdown.\n\n"
    "### Plan, Execute, Verify Workflow\n\n"
    "1.  **Plan:** Internally devise a step-by-step plan. Every action in the plan MUST be followed by a verification action (e.g., after writing a file, read it back; after a `git commit`, check the log).\n\n"
    "2.  **Execute:** Execute the plan sequentially. If any step fails, halt immediately and report the error, including the output of the failed command.\n\n"
    "3.  **Report:** Provide a concise summary of the final result. You MUST explicitly state how the final state was verified.\n"
    "    *   **Success Example:** 'Successfully created `app.zip` and verified its integrity by listing its contents.'\n"
    "    *   **Failure Example:** 'Failed to install dependencies. The `npm install` command exited with code 1. See error log above.'"
).strip()

_DEFAULT_SPECIAL_INSTRUCTION_PROMPT = (
    "### Guiding Principles\n"
    "- **Adhere to Conventions:** When working within a project, analyze existing code, files, and configuration to match its style and conventions. This is critical for pull requests.\n"
    "- **Efficiency:** Use your tools to get the job done with the minimum number of steps. Combine commands where possible (e.g., `mkdir -p`).\n\n"
    "### Expert Workflows\n"
    "- **Fixing a Bug:** First, try to write a failing test that reproduces the bug. Then, implement the fix and show that the test now passes.\n"
    "- **Code Changes:** After modifying code, first run tests directly related to the changed files. If they pass, then run the full project test suite before finishing.\n"
    "- **Research & Analysis:** Gather information from multiple reputable sources. Synthesize the information and cite the source URLs for factual claims."
).strip()


_DEFAULT_SUMMARIZATION_PROMPT = (
    "You are a Conversation Historian. Your task is to create a dense, "
    "structured snapshot of the conversation for the main assistant.\n\n"
    "You will receive a `Previous Summary` and the `Recent Conversation "
    "History`. Your goal is to produce an updated, rolling summary. Your "
    "output MUST be a single block of text with two sections:\n\n"
    "1.  `## Narrative Summary`\n"
    "    - **Identify Key Information:** From the `Recent Conversation "
    "History`, extract critical facts, user decisions, and final outcomes "
    "of tasks.\n"
    "    - **Integrate and Condense:** Integrate these key facts into the "
    "`Previous Summary`. Discard conversational filler and intermediate "
    "steps of completed tasks (e.g., 'User asked to see file X, I showed "
    "them' can be discarded if the file was just a step towards a larger "
    "goal). The summary should reflect the current state of the project or "
    "conversation, not a log of every single turn.\n\n"
    "2.  `## Transcript`\n"
    "    - The Transcript is the assistant's working memory. It MUST "
    "contain the last few turns of the conversation in full detail.\n"
    "    - **CRITICAL REQUIREMENT:** The assistant's and user's last response "
    "MUST be COPIED VERBATIM into the Transcript. DO NOT alter or truncate them."
).strip()


_DEFAULT_CONTEXT_ENRICHMENT_PROMPT = (
    "You are a Memory Curator. Your sole purpose is to produce a concise, "
    "up-to-date Markdown block of long-term context.\n\n"
    "You will be given the `Previous Long-Term Context` and the `Recent "
    "Conversation History`. Your job is to return a NEW, UPDATED version of "
    "the `Long-Term Context` by applying these rules:\n\n"
    "**Curation Heuristics:**\n"
    "- **Extract Stable Facts:** Identify durable information such as user "
    "preferences (e.g., 'I prefer tabs over spaces'), project-level "
    "decisions, or architectural choices.\n"
    "- **Integrate, Don't Just Append:** Update existing facts if new "
    "information overrides them. Merge related facts to keep the context "
    "dense.\n"
    "- **Discard Ephemeral Details:** Omit temporary states, resolved "
    "errors, and one-off requests that do not reflect a permanent preference "
    "or project state.\n"
    "- **Mark Dynamic Info:** For temporary information that must be "
    "retained (e.g., CWD, contents of a file being actively edited), you "
    "MUST add a note: `(short-term, must be re-verified)`."
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
        return _DEFAULT_SYSTEM_PROMPT

    @property
    def default_interactive_system_prompt(self) -> str:
        if self._default_interactive_system_prompt is not None:
            return self._default_interactive_system_prompt
        if CFG.LLM_INTERACTIVE_SYSTEM_PROMPT is not None:
            return CFG.LLM_INTERACTIVE_SYSTEM_PROMPT
        return _DEFAULT_INTERACTIVE_SYSTEM_PROMPT

    @property
    def default_persona(self) -> str:
        if self._default_persona is not None:
            return self._default_persona
        if CFG.LLM_PERSONA is not None:
            return CFG.LLM_PERSONA
        return _DEFAULT_PERSONA

    @property
    def default_special_instruction_prompt(self) -> str:
        if self._default_special_instruction_prompt is not None:
            return self._default_special_instruction_prompt
        if CFG.LLM_SPECIAL_INSTRUCTION_PROMPT is not None:
            return CFG.LLM_SPECIAL_INSTRUCTION_PROMPT
        return _DEFAULT_SPECIAL_INSTRUCTION_PROMPT

    @property
    def default_summarization_prompt(self) -> str:
        if self._default_summarization_prompt is not None:
            return self._default_summarization_prompt
        if CFG.LLM_SUMMARIZATION_PROMPT is not None:
            return CFG.LLM_SUMMARIZATION_PROMPT
        return _DEFAULT_SUMMARIZATION_PROMPT

    @property
    def default_context_enrichment_prompt(self) -> str:
        if self._default_context_enrichment_prompt is not None:
            return self._default_context_enrichment_prompt
        if CFG.LLM_CONTEXT_ENRICHMENT_PROMPT is not None:
            return CFG.LLM_CONTEXT_ENRICHMENT_PROMPT
        return _DEFAULT_CONTEXT_ENRICHMENT_PROMPT

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
