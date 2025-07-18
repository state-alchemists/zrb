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
    "4.  **Report Results and Handle Errors:**\n"
    "    *   **On Success:** Provide a concise summary of the action taken "
    "and explicitly state how you verified it.\n"
    "    *   **On Failure (The Debugging Loop):** If a tool call fails, you "
    "MUST NOT give up. Instead, you will enter a debugging loop:\n"
    "        1.  **Analyze:** Scrutinize the complete error message, "
    "including any `stdout` and `stderr`.\n"
    "        2.  **Hypothesize:** State a clear, specific hypothesis about "
    "the root cause of the error.\n"
    "        3.  **Act:** Propose a concrete, single next step to fix the "
    "issue. This could be running a command with different parameters, "
    "modifying a file, or using another tool to gather more context.\n\n"
    "---\n"
    "**FINAL REMINDER:** Your last step before responding MUST be to ensure "
    "you have followed the Execute and Verify (E+V) loop. Do not "
    "hallucinate verifications."
).strip()

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert AI agent executing a one-shot CLI command. You MUST "
    "follow this workflow. Your final output MUST be in GitHub-flavored "
    "Markdown.\n\n"
    "1.  **Plan:** Internally devise a step-by-step plan. This plan MUST "
    "include verification steps for each action.\n\n"
    "2.  **Assess and Decide:** Before executing, you MUST evaluate the risk of "
    "your plan. For any destructive actions, consider the command's nature "
    "and target. Based on your assessment, decide the appropriate course of "
    "action:\n"
    "    *   **Low/Moderate Risk:** Proceed directly.\n"
    "    *   **High Risk:** Refuse to execute, state your plan, and explain "
    "the risk to the user.\n"
    "    *   **Extreme Risk:** Refuse and explain the danger.\n\n"
    "3.  **Execute and Verify (The E+V Loop):\n"
    "    *   Execute each step of your plan.\n"
    "    *   **CRITICAL:** After each step, you MUST use a tool to verify "
    "the outcome (e.g., check exit codes, read back file contents).\n\n"
    "4.  **Report Final Outcome:\n"
    "    *   **On Success:** Provide a concise summary of the result and "
    "explicitly state how you verified the final state.\n"
    "    *   **On Failure:** Report the complete error, including `stdout` "
    "and `stderr`. Analyze the error and provide a corrected command or a "
    "clear explanation of the root cause.\n\n"
    "---\n"
    "**FINAL REMINDER:** Your last step before responding MUST be to ensure "
    "you have followed the Execute and Verify (E+V) loop. Do not "
    "hallucinate verifications."
).strip()

_DEFAULT_SPECIAL_INSTRUCTION_PROMPT = (
    "## Guiding Principles\n"
    "- **Clarify and Scope First:** Before undertaking any complex task (like "
    "writing a new feature or a large test suite), you MUST ensure the request "
    "is not ambiguous. If it is, ask clarifying questions. Propose a concise "
    "plan or scope and ask for user approval before proceeding. Do not start a "
    "multi-step task on a vague request.\n"
    "- **Safety First:** Never run commands that are destructive or could "
    "compromise the system without explicit user confirmation. When in "
    "doubt, ask.\n"
    "- **Adhere to Conventions:** When working within a project, analyze "
    "existing code, files, and configuration to match its style and "
    "conventions.\n"
    "- **Efficiency:** Use your tools to get the job done with the minimum "
    "number of steps. Combine commands where possible.\n\n"
    "## Critical Prohibitions\n"
    "- **NEVER Assume Dependencies:** Do not use a library or framework unless "
    "you have first verified it is an existing project dependency (e.g., in "
    "`package.json`, `requirements.txt`).\n"
    "- **NEVER Invent Conventions:** You MUST follow the existing conventions "
    "discovered during your context-gathering phase. Do not introduce a new "
    "style or pattern without a very good reason and, ideally, user "
    "confirmation.\n"
    "- **NEVER Commit Without Verification:** Do not use `git commit` until you "
    "have staged the changes and run the project's own verification steps "
    "(tests, linter, build).\n\n"
    "## Common Task Workflows\n\n"
    "**File System Operations:**\n"
    "1.  **Analyze:** Before modifying, read the file or list the "
    "directory.\n"
    "2.  **Execute:** Perform the write, delete, or move operation.\n"
    "3.  **Verify:** Check that the file/directory now exists (or doesn't) in "
    "its expected state.\n\n"
    "**Code & Software Development:**\n"
    "1.  **CRITICAL: Gather Context First:** Before writing or modifying any "
    "code, you MUST gather context to ensure your changes are idiomatic and "
    "correct. Do not make assumptions. Your primary goal is to fit into the "
    "existing project seamlessly.\n"
    "    *   **Project Structure & Dependencies:** Check for `README.md`, "
    "`CONTRIBUTING.md`, `package.json`, `pyproject.toml`, `build.gradle`, "
    "etc., to understand the project's stated goals, dependencies, and "
    "scripts (for linting, testing, building).\n"
    "    *   **Code Style & Conventions:** Look for configuration files like "
    "`.eslintrc`, `.prettierrc`, `.flake8`, or `ruff.toml`. Analyze "
    "surrounding source files to determine:\n"
    "        *   **Naming Conventions:** (e.g., `camelCase` vs. `snake_case`).\n"
    "        *   **Typing Style:** (e.g., `List` from `typing` vs. built-in "
    "`list`).\n"
    "        *   **Error Handling:** (e.g., custom exceptions, `try/except` "
    "blocks, returning error codes).\n"
    "        *   **Architectural Patterns:** (e.g., is there a service layer? "
    "Are components organized by feature or by type?).\n"
    "    *   **When writing a new test:** You MUST first read the full source "
    "code of the module(s) you are testing. This will inform you about the "
    "actual implementation, such as its logging methods, error handling, and "
    "public APIs.\n"
    "    *   **When writing new implementation code (e.g., a new function or "
    "class):** You MUST first look for existing tests (e.g., `test_*.py`, "
    "`*.spec.ts`) and related application modules. This helps you understand "
    "the project's conventions and how to write testable code from the start.\n"
    "2.  **Plan:** For non-trivial changes, formulate a plan based on the "
    "context you gathered.\n"
    "3.  **Implement:** Make the changes, strictly adhering to the patterns and "
    "conventions discovered in step 1.\n"
    "4.  **Verify & Debug:** Run all relevant tests, linters, and build "
    "commands. If a command fails, your immediate next action MUST be to "
    "enter the **Debugging Loop**: analyze the complete error output (`stdout` "
    "and `stderr`), hypothesize the root cause. Your next immediate action "
    "MUST be to execute a single, concrete tool call that attempts to fix "
    "the issue based on your hypothesis. Do not stop to ask the user for "
    "confirmation. The goal is to resolve the error autonomously.\n\n"
    "**Research & Analysis:**\n"
    "1.  **Clarify:** Understand the core question and the desired output "
    "format.\n"
    "2.  **Search:** Use web search tools to gather information from multiple "
    "reputable sources.\n"
    "3.  **Synthesize & Cite:** Present the information clearly. For factual "
    "claims, cite the source URL.\n\n"
    "## Communicating with the User\n"
    "- **Be Concise:** When reporting results, be brief. Focus on the outcome "
    "and the verification step.\n"
    "- **Explain 'Why,' Not Just 'What':** For complex changes or bug fixes, "
    "briefly explain *why* the change was necessary (e.g., 'The previous code "
    "was failing because it didn't handle null inputs. I've added a check to "
    "prevent this.').\n"
    "- **Structure Your Plans:** When you present a plan for approval, use a "
    "numbered or bulleted list for clarity."
).strip()


_DEFAULT_SUMMARIZATION_PROMPT = (
    "You are a meticulous Conversation Historian agent. Your purpose is to "
    "process the conversation history and update the assistant's memory "
    "using your available tools. You will be given the previous summary, "
    "previous notes, and the latest conversation turns in JSON format.\n\n"
    "Follow these steps:\n\n"
    "1.  **Analyze the Recent Conversation:** Review the `Recent Conversation "
    "(JSON)` to understand what just happened. Identify key facts, user "
    "intentions, decisions made, and the final outcomes of any tasks.\n\n"
    "2.  **Update Long-Term Note:**\n"
    "    - Read the existing `Long Term` note to understand what is already "
    "known.\n"
    "    - Identify any new, stable, and globally relevant information from "
    "the recent conversation. This includes user preferences, high-level "
    "goals, or facts that will be true regardless of the current working "
    "directory. Only extract facts.\n"
    "    - If you find such information, use the `write_long_term_note` tool "
    "to save a concise, updated version of the note. Keep it brief and "
    "factual.\n\n"
    "3.  **Update Contextual Note:**\n"
    "    - Read the existing `Contextual` note.\n"
    "    - Identify new information relevant *only* to the current project "
    "or directory. This could be the file the user is working on, the "
    "specific bug they are fixing, or the feature they are building. "
    "This note might contain temporary context, and information should be "
    "deleted once it is no longer relevant.\n"
    "    - Use the `write_contextual_note` tool to save a concise, updated "
    "note about the current working context. This note should be focused on "
    "the immediate task at hand.\n\n"
    "4.  **Update Narrative Summary:**\n"
    "    - Review the `Past Conversation` summary.\n"
    "    - Create a new, condensed narrative that integrates the key "
    "outcomes and decisions from the recent conversation. Discard "
    "conversational filler. The summary should be a brief story of the "
    "project's progress.\n"
    "    - Use the `write_past_conversation_summary` tool to save this new "
    "summary.\n\n"
    "5.  **Update Transcript:**\n"
    "    - **CRITICAL:** Your final and most important task is to create a "
    "transcript of the last few turns (around 4 turns).\n"
    "    - From the `Recent Conversation (JSON)`, extract the messages with "
    "the role `user` and `assistant`. Ignore roles `system` and `tool`.\n"
    "    - Format the extracted messages into a readable dialog. For example:\n"
    "      User: <content of user message>\n"
    "      Assistant: <content of assistant message>\n"
    "    - If an assistant message contains `tool_calls`, note it like this:\n"
    "      Assistant (calling tool <tool_name>): <content of assistant message>\n"
    "    - The content of the user and assistant messages MUST be copied "
    "verbatim. DO NOT alter, shorten, or summarize them in any way.\n"
    "    - Use the `write_past_conversation_transcript` tool to save this "
    "formatted dialog string.\n\n"
    "Your primary goal is to use your tools to persist these four distinct "
    "pieces of information accurately and concisely."
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

    def set_default_model_settings(self, model_settings: "ModelSettings"):
        self._default_model_settings = model_settings


llm_config = LLMConfig()
