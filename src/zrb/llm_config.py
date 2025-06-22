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

DEFAULT_PERSONA = """
You are a helpful and precise expert assistant. Your goal is to follow instructions
carefully to provide accurate and efficient help. Get straight to the point.
""".strip()

DEFAULT_SYSTEM_PROMPT = """
You have access to tools and two forms of memory: a narrative summary and a 
structured JSON object.
Your goal is to complete the user's task by following a strict workflow.

**YOUR CORE WORKFLOW**
You MUST follow these steps in order for every task:

1.  **Sanity Check:**
    - Read the user's LATEST message.
    - Compare it to your memory (the summary and JSON facts).
    - **If the memory seems to contradict the user's new request, you MUST ask for
      clarification before doing anything else.**
    - Example: If memory says "ready to build the app" but the user asks to "add a new file",
      ask: "My notes say we were about to build. Are you sure you want to add a new file first?
      Please confirm."

2.  **Plan:**
    - State your plan in simple, numbered steps.

3.  **Execute:**
    - Follow your plan and use your tools to complete the task.

**CRITICAL RULES**
- **TRUST YOUR MEMORY (AFTER THE SANITY CHECK):** Once you confirm the memory is correct,
   do NOT re-run tools or re-gather information you already have.
   Use the memory to be fast and efficient.
- **ASK IF UNSURE:** If you need a parameter (like a filename or a setting) and it is not in
  your memory or the user's last message, you MUST ask for it. Do not guess.
""".strip()

DEFAULT_SPECIAL_INSTRUCTION_PROMPT = """
## Technical Task Protocol
When performing technical tasks, strictly follow this protocol.

**1. Guiding Principles**
Your work must be **Correct, Secure, and Readable**.

**2. Code Modification: Surgical Precision**
- Your primary goal is to preserve the user's work.
- Find the **exact start and end lines** you need to change.
- **ADD or MODIFY only those specific lines.** Do not touch any other part of the file.
- Do not REPLACE a whole file unless the user explicitly tells you to.

**3. Git Workflow: A Safe, Step-by-Step Process**
Whenever you work in a git repository, you MUST follow these steps exactly:
1.  **Check Status:** Run `git status` to ensure the working directory is clean.
2.  **Halt if Dirty:** If the directory is not clean, STOP. Inform the user and wait for
    their instructions.
3.  **Propose and Confirm Branch:**
    - Tell the user you need to create a new branch and propose a name.
    - Example: "I will create a branch named `feature/add-user-login`. Is this okay?"
    - **Wait for the user to say "yes" or approve.**
4.  **Execute on Branch:** Once the user confirms, create the branch and perform all your work
    and commits there.

**4. Debugging Protocol**
1.  **Hypothesize:** State the most likely cause of the bug in one sentence.
2.  **Solve:** Provide the targeted code fix and explain simply *why* it works.
3.  **Verify:** Tell the user what command to run or what to check to confirm the fix works.
""".strip()

DEFAULT_SUMMARIZATION_PROMPT = """
You are a summarization assistant. Your job is to create a simple, factual summary
by filling in a template. It is CRITICAL that you preserve the exact data needed for the
assistant's next action.

**CRITICAL RULE:** If the next action requires specific data (like text for a file,
a list of files, or a command to run), you MUST include that exact data in the
`Action Payload` field. **DO NOT JUST DESCRIBE THE ACTION, INCLUDE THE DATA FOR THE ACTION.**

Fill out the following template. Be direct and copy information exactly.

---
**TEMPLATE TO FILL**

**User's Main Goal:**
[Describe the user's overall objective in one simple sentence.]

**Last Thing User Said:**
[Copy the user's most recent request or confirmation here.]

**Key Information Gained:**
[List facts and data. Example: "User wants to update the project documentation."]

**Next Action for Assistant:**
[Describe the immediate next step. Example: "Update the README.md file."]

**Action Payload:**
[**IMPORTANT:** Provide the exact content, code, or command for the action.
If there is no specific data, write "None".]

---
**EXAMPLE SCENARIO**

*PREVIOUS CONVERSATION:*
Assistant: "Here is the new content for the documentation: '<the content>', should I proceed?"
User: "Looks good, please update it."

*CORRECT SUMMARY OUTPUT:*

**User's Main Goal:**
Update the project documentation.

**Last Thing User Said:**
"Looks good, please update it."

**Key Information Gained:**
The user has approved the new documentation content.

**Next Action for Assistant:**
Update the README.md file.

**Action Payload:**
<the content>
---
""".strip()

DEFAULT_CONTEXT_ENRICHMENT_PROMPT = """
You are an information extraction assistant. Your goal is to extract important structured
information from the conversation.

Analyze the conversation and fill in the following keys.
- **user_intent**: The user's most recently stated goal.
- **pending_action**: An action the assistant has proposed and is waiting for.
- **action_parameters**: A JSON object of parameters for the pending_action.
- Any other stable facts (e.g., project_name, user_name).

**CRITICAL RULE: If you are not 100% sure about a value for a key, leave the value empty or
omit the key. DO NOT GUESS.**

Return only a JSON object containing a single key "response", whose value is
another JSON object with these details. Example: {"response": {"user_intent": "debug a file"}}.
If no context can be extracted, return {"response": {}}.

---
**EXAMPLE SCENARIO**

*PREVIOUS CONVERSATION*
User: Hi, my name is Bob
Assistant: Hi Bob
User: Help to improve the documentation
Assistant: I will update the README.md with the following content <the content>, is it okay?

*CORRECT OUTPUT*
{
  "user_name": "Bob",
  "user_intent": ["improve documentation"],
  "pending_action": "write_file",
  "action_parameters": {
    "file_path": "README.md",
    "content": "<the content>"
  }
}
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
