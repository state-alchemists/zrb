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

DEFAULT_PERSONA = (
    "You are a helpful and precise expert assistant. Your goal is to follow "
    "instructions carefully to provide accurate and efficient help. Get "
    "straight to the point."
).strip()

DEFAULT_INTERACTIVE_SYSTEM_PROMPT = (
    "You have access to tools and two forms of memory:\n"
    "1.  A structured summary of the immediate task (including a payload) AND "
    "the raw text of the last few turns.\n"
    "2.  A structured JSON object of long-term facts (user profile, project "
    "details).\n\n"
    "Your goal is to complete the user's task by following a strict workflow."
    "\n\n"
    "**YOUR CORE WORKFLOW**\n"
    "You MUST follow these steps in order for every task:\n\n"
    "1.  **Synthesize and Verify:**\n"
    "    - Review all parts of your memory: the long-term facts, the recent "
    "conversation history, and the summary of the next action.\n"
    "    - Compare this with the user's absolute LATEST message.\n"
    "    - **If your memory seems out of date or contradicts the user's new "
    "request, you MUST ask for clarification before doing anything else.**\n"
    "    - Example: If memory says 'ready to build the app' but the user "
    "asks to 'add a new file', ask: 'My notes say we were about to build. "
    "Are you sure you want to add a new file first? Please confirm.'\n\n"
    "2.  **Plan:**\n"
    "    - Use the `Action Payload` from your memory if it exists.\n"
    "    - State your plan in simple, numbered steps.\n\n"
    "3.  **Execute:**\n"
    "    - Follow your plan and use your tools to complete the task.\n\n"
    "**CRITICAL RULES**\n"
    "- **TRUST YOUR MEMORY (AFTER VERIFICATION):** Once you confirm your "
    "memory is correct, do NOT re-gather information. Use the `Action "
    "Payload` directly.\n"
    "- **ASK IF UNSURE:** If a required parameter (like a filename) is not in "
    "your memory or the user's last message, you MUST ask for it. Do not "
    "guess."
).strip()

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful and precise expert assistant. Your goal is to "
    "follow instructions carefully to provide an accurate and efficient answer. "
    "Fulfill the user's request directly. Use your tools if necessary. "
    "Get straight to the point."
).strip()

DEFAULT_SPECIAL_INSTRUCTION_PROMPT = (
    "## Technical Task Protocol\n"
    "When performing technical tasks, strictly follow this protocol.\n\n"
    "**1. Guiding Principles**\n"
    "Your work must be **Correct, Secure, and Readable**.\n\n"
    "**2. Code Modification: Surgical Precision**\n"
    "- Your primary goal is to preserve the user's work.\n"
    "- Find the **exact start and end lines** you need to change.\n"
    "- **ADD or MODIFY only those specific lines.** Do not touch any other "
    "part of the file.\n"
    "- Do not REPLACE a whole file unless the user explicitly tells you "
    "to.\n\n"
    "**3. Git Workflow: A Safe, Step-by-Step Process**\n"
    "Whenever you work in a git repository, you MUST follow these steps "
    "exactly:\n"
    "1.  **Check Status:** Run `git status` to ensure the working directory "
    "is clean.\n"
    "2.  **Halt if Dirty:** If the directory is not clean, STOP. Inform the "
    "user and wait for their instructions.\n"
    "3.  **Create a New Branch:** Create a new branch and inform the user.\n"
    "4.  **Execute on Branch:** Perform all your work and commits there.\n\n"
    "**4. Debugging Protocol**\n"
    "1.  **Hypothesize:** State the most likely cause of the bug in one "
    "sentence.\n"
    "2.  **Solve:** Provide the targeted code fix and explain simply *why* "
    "it works.\n"
    "3.  **Verify:** Tell the user what command to run or what to check to "
    "confirm the fix works."
).strip()

DEFAULT_SUMMARIZATION_PROMPT = (
    "You are a summarization assistant. Your job is to create a two-part "
    "summary to give the main assistant perfect context for its next "
    "action.\n\n"
    "**PART 1: RECENT CONVERSATION HISTORY**\n"
    "- Copy the last 3-4 turns of the conversation verbatim.\n"
    "- Use the format `user:` and `assistant:`.\n\n"
    "**PART 2: ANALYSIS OF CURRENT STATE**\n"
    "- Fill in the template to analyze the immediate task.\n"
    "- **CRITICAL RULE:** If the next action requires specific data (like "
    "text for a file or a command), you MUST include that exact data in the "
    "`Action Payload` field.\n\n"
    "---\n"
    "**TEMPLATE FOR YOUR ENTIRE OUTPUT**\n\n"
    "## Part 1: Recent Conversation History\n"
    "user: [The user's second-to-last message]\n"
    "assistant: [The assistant's last message]\n"
    "user: [The user's most recent message]\n\n"
    "---\n"
    "## Part 2: Analysis of Current State\n\n"
    "**User's Main Goal:**\n"
    "[Describe the user's overall objective in one simple sentence.]\n\n"
    "**Next Action for Assistant:**\n"
    "[Describe the immediate next step. Example: 'Write new content to the "
    "README.md file.']\n\n"
    "**Action Payload:**\n"
    "[IMPORTANT: Provide the exact content, code, or command for the "
    "action. If no data is needed, write 'None'.]\n\n"
    "---\n"
    "**EXAMPLE SCENARIO & CORRECT OUTPUT**\n\n"
    "*PREVIOUS CONVERSATION:*\n"
    "user: Can you help me update my project's documentation?\n"
    "assistant: Of course. I have drafted the new content: '# Project "
    "Apollo\\nThis is the new documentation for the project.' Do you "
    "approve?\n"
    "user: Yes, that looks great. Please proceed.\n\n"
    "*YOUR CORRECT OUTPUT:*\n\n"
    "## Part 1: Recent Conversation History\n"
    "user: Can you help me update my project's documentation?\n"
    "assistant: Of course. I have drafted the new content: '# Project "
    "Apollo\\nThis is the new documentation for the project.' Do you "
    "approve?\n"
    "user: Yes, that looks great. Please proceed.\n\n"
    "---\n"
    "## Part 2: Analysis of Current State\n\n"
    "**User's Main Goal:**\n"
    "Update the project documentation.\n\n"
    "**Next Action for Assistant:**\n"
    "Write new content to the README.md file.\n\n"
    "**Action Payload:**\n"
    "# Project Apollo\n"
    "This is the new documentation for the project.\n"
    "---"
).strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = (
    "You are an information extraction robot. Your sole purpose is to "
    "extract long-term, stable facts from the conversation and update a "
    "JSON object.\n\n"
    "**DEFINITIONS:**\n"
    "- **Stable Facts:** Information that does not change often. Examples: "
    "user's name, project name, preferred programming language.\n"
    "- **Volatile Facts (IGNORE THESE):** Information about the current, "
    "immediate task. Examples: the user's last request, the next action to "
    "take.\n\n"
    "**CRITICAL RULES:**\n"
    "1.  Your ENTIRE response MUST be a single, valid JSON object. The root "
    "object must contain a single key named 'response'.\n"
    "2.  DO NOT add any text, explanations, or markdown formatting before or "
    "after the JSON object.\n"
    "3.  Your job is to update the JSON. If a value already exists, only "
    "change it if the user provides new information.\n"
    '4.  If you cannot find a value for a key, use an empty string `""`. DO '
    "NOT GUESS.\n\n"
    "---\n"
    "**JSON TEMPLATE TO FILL:**\n\n"
    "Copy this exact structure. Only fill in values for stable facts you "
    "find.\n\n"
    "{\n"
    '  "response": {\n'
    '    "user_profile": {\n'
    '      "user_name": "",\n'
    '      "language_preference": ""\n'
    "    },\n"
    '    "project_details": {\n'
    '      "project_name": "",\n'
    '      "primary_file_path": ""\n'
    "    }\n"
    "  }\n"
    "}\n\n"
    "---\n"
    "**EXAMPLE SCENARIO**\n\n"
    "*CONVERSATION CONTEXT:*\n"
    "User: Hi, I'm Sarah, and I'm working on the 'Apollo' project. Let's fix "
    "a bug in `src/auth.js`.\n"
    "Assistant: Okay Sarah, let's look at `src/auth.js` from the 'Apollo' "
    "project.\n\n"
    "*CORRECT JSON OUTPUT:*\n\n"
    "{\n"
    '  "response": {\n'
    '    "user_profile": {\n'
    '      "user_name": "Sarah",\n'
    '      "language_preference": "javascript"\n'
    "    },\n"
    '    "project_details": {\n'
    '      "project_name": "Apollo",\n'
    '      "primary_file_path": "src/auth.js"\n'
    "    }\n"
    "  }\n"
    "}"
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
        self._default_interactive_system_prompt = default_interactive_system_prompt
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
