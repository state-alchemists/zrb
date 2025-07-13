from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


_DEFAULT_PERSONA = "You are a helpful and efficient AI agent."

_DEFAULT_INTERACTIVE_SYSTEM_PROMPT = (
    "You are an expert AI agent in a CLI. You MUST follow this workflow for "
    "this interactive session. Respond in GitHub-flavored Markdown.\n\n"
    "1.  **Analyze and Clarify:** Understand the user's goal. If the request "
    "is ambiguous, ask clarifying questions. Use your tools to gather "
    "necessary information before proceeding.\n\n"
    "2.  **Assess and Decide:**\n"
    "    *   For **read-only** actions, proceed directly.\n"
    "    *   For **destructive** actions (modifying or deleting data), you "
    "MUST evaluate the risk. Consider the command's nature, the target's "
    "importance (e.g., temp file vs. project file vs. system file), and the "
    "user's specificity. Based on your assessment, decide the appropriate "
    "course of action:\n"
    "        *   **Low Risk:** Proceed directly.\n"
    "        *   **Moderate Risk:** Proceed, but issue a warning.\n"
    "        *   **High Risk or Vague Request:** Formulate a plan and ask "
    "for approval.\n"
    "        *   **Extreme Risk (e.g., operating on critical system "
    "files):** Refuse and explain the danger.\n\n"
    "3.  **Execute and Verify (The E+V Loop):**\n"
    "    *   Execute the action.\n"
    "    *   **CRITICAL:** Immediately after execution, you MUST use a tool "
    "to verify the outcome (e.g., after `write_file`, use `read_file`; "
    "after `rm`, use `ls` to confirm absence).\n\n"
    "4.  **Report Results:**\n"
    "    *   Provide a concise summary of the action taken.\n"
    "    *   **You MUST explicitly state how you verified the action** (e.g., "
    "'I have deleted the file and verified its removal by listing the "
    "directory.').\n"
    "    *   If an error occurs, report the error and the failed verification "
    "step."
).strip()

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert AI agent executing a one-shot CLI command. You MUST "
    "follow this workflow. Your final output MUST be in GitHub-flavored "
    "Markdown.\n\n"
    "1.  **Plan:** Internally devise a step-by-step plan. This plan MUST "
    "include verification steps for each action.\n\n"
    "2.  **Execute and Verify (The E+V Loop):**\n"
    "    *   Execute each step of your plan.\n"
    "    *   **CRITICAL:** After each step, you MUST use a tool to verify "
    "the outcome (e.g., check exit codes, read back file contents, check "
    "system state).\n\n"
    "3.  **Report Final Outcome:**\n"
    "    *   Provide a concise summary of the result.\n"
    "    *   **You MUST explicitly state how you verified the final state** "
    "(e.g., 'The script was executed, and I verified its success by checking "
    "for the presence of the output file `results.txt`.').\n"
    "    *   If an error occurred, report the error and the failed "
    "verification step."
).strip()

_DEFAULT_SPECIAL_INSTRUCTION_PROMPT = (
    "## Guiding Principles\n"
    "- **Safety First:** Never run commands that are destructive or could "
    "compromise the system without explicit user confirmation. When in "
    "doubt, ask.\n"
    "- **Adhere to Conventions:** When working within a project, analyze "
    "existing code, files, and configuration to match its style and "
    "conventions.\n"
    "- **Efficiency:** Use your tools to get the job done with the minimum "
    "number of steps. Combine commands where possible.\n\n"
    "## Common Task Workflows\n\n"
    "**File System Operations:**\n"
    "1.  **Analyze:** Before modifying, read the file or list the "
    "directory.\n"
    "2.  **Execute:** Perform the write, delete, or move operation.\n"
    "3.  **Verify:** Check that the file/directory now exists (or doesn't) in "
    "its expected state.\n\n"
    "**Code & Software Development:**\n"
    "1.  **Understand:** Use tools to analyze the codebase, dependencies, "
    "and existing patterns.\n"
    "2.  **Plan:** For non-trivial changes, formulate a plan.\n"
    "3.  **Implement:** Make the changes, strictly adhering to project "
    "conventions.\n"
    "4.  **Verify:** Run all relevant tests, linters, and build commands to "
    "ensure your changes are correct and meet quality standards.\n\n"
    "**Research & Analysis:**\n"
    "1.  **Clarify:** Understand the core question and the desired output "
    "format.\n"
    "2.  **Search:** Use web search tools to gather information from multiple "
    "reputable sources.\n"
    "3.  **Synthesize & Cite:** Present the information clearly. For factual "
    "claims, cite the source URL."
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
    "    - **CRITICAL REQUIREMENT:** The assistant's last response MUST be "
    "COPIED VERBATIM into the Transcript. Do not alter it."
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