"""LLM prompt config: prompt dirs, tool-call visibility, system-prompt include toggles."""

from __future__ import annotations

import os

from zrb.config.helper import get_env
from zrb.util.string.conversion import to_boolean


class LLMPromptMixin:
    def __init__(self):
        self.DEFAULT_LLM_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_BASE_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_SHOW_TOOL_CALL_DETAIL: str = "off"
        self.DEFAULT_LLM_SHOW_TOOL_CALL_RESULT: str = "off"
        self.DEFAULT_LLM_INCLUDE_PERSONA: str = "on"
        self.DEFAULT_LLM_INCLUDE_MANDATE: str = "on"
        self.DEFAULT_LLM_INCLUDE_GIT_MANDATE: str = "on"
        self.DEFAULT_LLM_INCLUDE_SYSTEM_CONTEXT: str = "on"
        self.DEFAULT_LLM_INCLUDE_JOURNAL: str = "on"
        self.DEFAULT_LLM_INCLUDE_CLAUDE_SKILLS: str = "on"
        self.DEFAULT_LLM_INCLUDE_CLI_SKILLS: str = "off"
        self.DEFAULT_LLM_INCLUDE_PROJECT_CONTEXT: str = "on"
        self.DEFAULT_LLM_INCLUDE_TOOL_GUIDANCE: str = "on"
        super().__init__()

    @property
    def LLM_PROMPT_DIR(self) -> str:
        default = self.DEFAULT_LLM_PROMPT_DIR
        if default == "":
            default = os.path.join(f".{self.ROOT_GROUP_NAME}", "llm", "prompt")
        return get_env("LLM_PROMPT_DIR", default, self.ENV_PREFIX)

    @LLM_PROMPT_DIR.setter
    def LLM_PROMPT_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_PROMPT_DIR"] = value

    @property
    def LLM_BASE_PROMPT_DIR(self) -> str:
        return get_env(
            "LLM_BASE_PROMPT_DIR",
            self.DEFAULT_LLM_BASE_PROMPT_DIR,
            self.ENV_PREFIX,
        )

    @LLM_BASE_PROMPT_DIR.setter
    def LLM_BASE_PROMPT_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_BASE_PROMPT_DIR"] = value

    @property
    def LLM_SHOW_TOOL_CALL_DETAIL(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_SHOW_TOOL_CALL_DETAIL",
                self.DEFAULT_LLM_SHOW_TOOL_CALL_DETAIL,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHOW_TOOL_CALL_DETAIL.setter
    def LLM_SHOW_TOOL_CALL_DETAIL(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHOW_TOOL_CALL_DETAIL"] = (
            "on" if value else "off"
        )

    @property
    def LLM_SHOW_TOOL_CALL_RESULT(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_SHOW_TOOL_CALL_RESULT",
                self.DEFAULT_LLM_SHOW_TOOL_CALL_RESULT,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHOW_TOOL_CALL_RESULT.setter
    def LLM_SHOW_TOOL_CALL_RESULT(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHOW_TOOL_CALL_RESULT"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_PERSONA(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_PERSONA",
                self.DEFAULT_LLM_INCLUDE_PERSONA,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_PERSONA.setter
    def LLM_INCLUDE_PERSONA(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_PERSONA"] = "on" if value else "off"

    @property
    def LLM_INCLUDE_MANDATE(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_MANDATE",
                self.DEFAULT_LLM_INCLUDE_MANDATE,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_MANDATE.setter
    def LLM_INCLUDE_MANDATE(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_MANDATE"] = "on" if value else "off"

    @property
    def LLM_INCLUDE_GIT_MANDATE(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_GIT_MANDATE",
                self.DEFAULT_LLM_INCLUDE_GIT_MANDATE,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_GIT_MANDATE.setter
    def LLM_INCLUDE_GIT_MANDATE(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_GIT_MANDATE"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_SYSTEM_CONTEXT(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_SYSTEM_CONTEXT",
                self.DEFAULT_LLM_INCLUDE_SYSTEM_CONTEXT,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_SYSTEM_CONTEXT.setter
    def LLM_INCLUDE_SYSTEM_CONTEXT(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_SYSTEM_CONTEXT"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_JOURNAL(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_JOURNAL",
                self.DEFAULT_LLM_INCLUDE_JOURNAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_JOURNAL.setter
    def LLM_INCLUDE_JOURNAL(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_JOURNAL"] = "on" if value else "off"

    @property
    def LLM_INCLUDE_JOURNAL_MANDATE(self) -> bool:
        explicit = os.environ.get(f"{self.ENV_PREFIX}_LLM_INCLUDE_JOURNAL_MANDATE")
        if explicit is not None:
            return to_boolean(explicit)
        return self.LLM_INCLUDE_JOURNAL

    @LLM_INCLUDE_JOURNAL_MANDATE.setter
    def LLM_INCLUDE_JOURNAL_MANDATE(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_JOURNAL_MANDATE"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_JOURNAL_REMINDER(self) -> bool:
        explicit = os.environ.get(f"{self.ENV_PREFIX}_LLM_INCLUDE_JOURNAL_REMINDER")
        if explicit is not None:
            return to_boolean(explicit)
        return self.LLM_INCLUDE_JOURNAL

    @LLM_INCLUDE_JOURNAL_REMINDER.setter
    def LLM_INCLUDE_JOURNAL_REMINDER(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_JOURNAL_REMINDER"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_CLAUDE_SKILLS(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_CLAUDE_SKILLS",
                self.DEFAULT_LLM_INCLUDE_CLAUDE_SKILLS,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_CLAUDE_SKILLS.setter
    def LLM_INCLUDE_CLAUDE_SKILLS(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_CLAUDE_SKILLS"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_CLI_SKILLS(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_CLI_SKILLS",
                self.DEFAULT_LLM_INCLUDE_CLI_SKILLS,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_CLI_SKILLS.setter
    def LLM_INCLUDE_CLI_SKILLS(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_CLI_SKILLS"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_PROJECT_CONTEXT(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_PROJECT_CONTEXT",
                self.DEFAULT_LLM_INCLUDE_PROJECT_CONTEXT,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_PROJECT_CONTEXT.setter
    def LLM_INCLUDE_PROJECT_CONTEXT(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_PROJECT_CONTEXT"] = (
            "on" if value else "off"
        )

    @property
    def LLM_INCLUDE_TOOL_GUIDANCE(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_TOOL_GUIDANCE",
                self.DEFAULT_LLM_INCLUDE_TOOL_GUIDANCE,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_TOOL_GUIDANCE.setter
    def LLM_INCLUDE_TOOL_GUIDANCE(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_TOOL_GUIDANCE"] = (
            "on" if value else "off"
        )
