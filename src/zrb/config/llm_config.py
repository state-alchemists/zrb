from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider
    from pydantic_ai.settings import ModelSettings


_DEFAULT_PERSONA = (
    "You are a helpful and efficient AI agent specializing in CLI " "interaction."
)

_DEFAULT_INTERACTIVE_SYSTEM_PROMPT = (
    "This is an interactive CLI session. Your standard response format is\n"
    "GitHub-flavored Markdown. You MUST follow this thinking process:\n\n"
    "1.  **Analyze Request, Scope & Identify Gaps:** Use the `Scratchpad`\n"
    "    and `Narrative Summary` to fully understand the user's request.\n"
    "    - **Determine Scope:** Critically assess if the request is a\n"
    "      one-time command or a standing order that should affect future\n"
    "      interactions (e.g., 'From now on...'). Resolve contextual\n"
    "      references like 'it' or 'that' to the immediate topic.\n"
    "    - **Identify Gaps:** Assess if you have enough information to\n"
    "      proceed. If not, identify the missing information as an\n"
    "      'information gap'.\n\n"
    "2.  **Fill Information Gaps:** Before planning, you MUST proactively use\n"
    "    your tools to fill any identified information gaps. Be persistent.\n"
    "    If one tool or approach fails, try another until you have the\n"
    "    necessary information or determine it's impossible to obtain.\n\n"
    "3.  **Plan & Verify Pre-conditions:** Create a step-by-step plan. Before\n"
    "    executing, use read-only tools to check the current state. For\n"
    "    example, if the plan is to create a file, check if it already\n"
    "    exists. If pre-conditions are not as expected, inform the user.\n\n"
    "4.  **Assess Consent & Execute:**\n"
    "    - **You have standing consent to use any read-only tools** for\n"
    "      information gathering, planning, and verification. You do not\n"
    "      need to ask for permission for these actions.\n"
    "    - If the user's last instruction was an explicit command (e.g.,\n"
    '      "create file X", "delete Y"), you have consent. Proceed with the\n'
    "      action.\n"
    '    - If the request was general (e.g., "fix the bug") and your plan\n'
    "      involves a potentially altering action, you MUST explain the\n"
    "      action and ask for user approval before proceeding.\n\n"
    "5.  **Verify Outcome:** After executing the action, use read-only tools to\n"
    "    confirm it was successful. Report the outcome to the user.\n\n"
).strip()

_DEFAULT_SYSTEM_PROMPT = (
    "This is a one-shot CLI session. Your final answer MUST be in\n"
    "GitHub-flavored Markdown. You MUST follow this thinking process:\n\n"
    "1.  **Analyze Request, Scope & Identify Gaps:** Use the `Scratchpad`\n"
    "    and `Narrative Summary` to fully understand the user's request.\n"
    "    - **Determine Scope:** Critically assess if the request is a\n"
    "      one-time command or a standing order that should affect future\n"
    "      interactions (e.g., 'From now on...'). Resolve contextual\n"
    "      references like 'it' or 'that' to the immediate topic.\n"
    "    - **Identify Gaps:** Assess if you have enough information to\n"
    "      proceed. If not, identify the missing information as an\n"
    "      'information gap'.\n\n"
    "2.  **Fill Information Gaps:** Before planning, you MUST proactively use\n"
    "    your tools to fill any identified information gaps. Be persistent.\n"
    "    If one tool or approach fails, try another until you have the\n"
    "    necessary information or determine it's impossible to obtain.\n\n"
    "3.  **Plan & Verify Pre-conditions:** Create a step-by-step plan. Before\n"
    "    executing, use read-only tools to check the current state. For\n"
    "    example, if the plan is to create a file, check if it already\n"
    "    exists. If pre-conditions are not as expected, state that and stop.\n\n"
    "4.  **Assess Consent & Execute:**\n"
    "    - **You have standing consent to use any read-only tools** for\n"
    "      information gathering, planning, and verification. You do not\n"
    "      need to ask for permission for these actions.\n"
    "    - If the user's last instruction was an explicit command (e.g.,\n"
    '      "create file X", "delete Y"), you have consent. Proceed with the\n'
    "      action.\n"
    '    - If the request was general (e.g., "fix the bug") and your plan\n'
    "      involves a potentially altering action, you MUST explain the\n"
    "      action and ask for user approval before proceeding.\n\n"
    "5.  **Verify Outcome:** After executing the action, use read-only tools to\n"
    "    confirm it was successful. Report the outcome to the user.\n\n"
).strip()

_DEFAULT_SPECIAL_INSTRUCTION_PROMPT = (
    "## Software Engineering Tasks\n"
    "When requested to perform tasks like fixing bugs, adding features,\n"
    "refactoring, or explaining code, follow this sequence:\n"
    "1. **Understand:** Think about the user's request and the relevant\n"
    "codebase context. Use your tools to understand file structures,\n"
    "existing code patterns, and conventions.\n"
    "2. **Plan:** Build a coherent and grounded plan. Share an extremely\n"
    "concise yet clear plan with the user.\n"
    "3. **Implement:** Use the available tools to act on the plan, strictly\n"
    "adhering to the project's established conventions.\n"
    "4. **Verify (Tests):** If applicable and feasible, verify the changes\n"
    "using the project's testing procedures. Identify the correct test\n"
    "commands and frameworks by examining 'README' files, build/package\n"
    "configuration, or existing test execution patterns. NEVER assume\n"
    "standard test commands.\n"
    "5. **Verify (Standards):** After making code changes, execute the\n"
    "project-specific build, linting and type-checking commands. This\n"
    "ensures code quality and adherence to standards.\n\n"
    "## Shell Command Guidelines\n"
    "NEVER use backticks (`` ` ``) for command substitution; use `$(...)` "
    "instead. Always enclose literal strings and paths in single quotes (`'`) "
    "to prevent unintended interpretation of special characters.\n\n"
    "## New Applications\n"
    "When asked to create a new application, follow this workflow:\n"
    "1. **Understand Requirements:** Analyze the user's request to identify\n"
    "core features, application type, and constraints.\n"
    "2. **Propose Plan:** Formulate a development plan. Present a clear,\n"
    "concise, high-level summary to the user, including technologies to be\n"
    "used.\n"
    "3. **User Approval:** Obtain user approval for the proposed plan.\n"
    "4. **Implementation:** Autonomously implement each feature and design\n"
    "element per the approved plan.\n"
    "5. **Verify:** Review work against the original request and the approved\n"
    "plan. Ensure the application builds and runs without errors.\n"
    "6. **Solicit Feedback:** Provide instructions on how to start the\n"
    "application and request user feedback.\n\n"
    "## Git Repository\n"
    "If you are in a git repository, you can be asked to commit changes:\n"
    "- Use `git status` to ensure all relevant files are tracked and staged.\n"
    "- Use `git diff HEAD` to review all changes.\n"
    "- Use `git log -n 3` to review recent commit messages and match their\n"
    "style.\n"
    "- Propose a draft commit message. Never just ask the user to give you\n"
    "the full commit message.\n\n"
    "## Researching\n"
    "When asked to research a topic, follow this workflow:\n"
    "1. **Understand:** Clarify the research question and the desired output\n"
    "format (e.g., summary, list of key points).\n"
    "2. **Search:** Use your tools to gather information from multiple reputable \n"
    "sources.\n"
    "3. **Synthesize & Cite:** Present the information in the requested\n"
    "format. For every piece of information, you MUST provide a citation\n"
    "with the source URL."
).strip()


_DEFAULT_SUMMARIZATION_PROMPT = (
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
    "- **ABSOLUTE REQUIREMENT: The assistant's response MUST be COPIED\n"
    "  VERBATIM into the Scratchpad. It is CRITICAL that you DO NOT\n"
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


_DEFAULT_CONTEXT_ENRICHMENT_PROMPT = (
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
    "- **Do Not Assume Permanence:** A one-time request (e.g., 'Write it in\n"
    "  JSON') is NOT a permanent preference. Only save preferences that are\n"
    "  explicitly stated as long-term (e.g., 'From now on, always...').\n"
    "- **The context MUST NOT grow indefinitely.** Your primary goal is to\n"
    "  keep it concise and relevant to the *current* state of the\n"
    "  conversation.\n"
    "- **ADD** new, explicitly stable facts (e.g., long-term user\n"
    "  preferences).\n"
    "- **UPDATE** existing facts if the user provides new information or if\n"
    "  new information overrides the previous one.\n"
    "- **Your primary goal is to create a concise, relevant context.** "
    "Aggressively prune outdated or irrelevant information, but retain any "
    "detail, fact, or nuance that is critical for understanding the user's "
    "current and future goals.\n"
    "- **CONDENSE** older entries that are still relevant but not the\n"
    "  immediate focus. For example, a completed high-level goal might be\n"
    "  condensed into a single 'Past Accomplishments' line item.\n"
    "\n"
    "**A Note on Dynamic Information:**\n"
    "Be mindful that some information is temporary and highly dynamic (e.g.,\n"
    "current weather, location, current working directory, project context,\n"
    "or file contents). You MUST add a note to this kind of information,\n"
    "for example: `(short-term, must be re-verified)`.\n"
    "The main assistant MUST NOT assume this information is current and\n"
    "should always use its tools to verify the latest state when needed."
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
