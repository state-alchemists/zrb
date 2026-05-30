"""LLM prompt config: prompt dirs, tool-call visibility, include-sections list."""

from __future__ import annotations

import os

from zrb.config.helper import get_env
from zrb.util.string.conversion import to_boolean


class LLMPromptMixin:
    ENV_PREFIX: str
    ROOT_GROUP_NAME: str

    def __init__(self):
        self.DEFAULT_LLM_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_BASE_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_SHOW_TOOL_CALL_DETAIL: str = "off"
        self.DEFAULT_LLM_SHOW_TOOL_CALL_RESULT: str = "off"
        # Comma-separated, order-sensitive list of prompt sections to include.
        # Order in the list determines the order they appear in the system prompt.
        # Each section is MECE (mutually exclusive in concern): persona=identity+priorities,
        # mandate=operating rules, git_mandate=git approval, journal_mandate=memory protocol,
        # system_context=runtime facts, project_context=AGENTS.md/CLAUDE.md,
        # tool_guidance=per-tool rules, claude_skills=catalogue.
        self.DEFAULT_LLM_INCLUDE_SECTIONS: str = (
            "persona,mandate,git_mandate,journal_mandate,system_context,"
            "project_context,tool_guidance,claude_skills"
        )
        # Runtime journaling reminder — separate from the journal_mandate
        # prompt section, which is controlled by LLM_INCLUDE_SECTIONS.
        self.DEFAULT_LLM_INCLUDE_JOURNAL_REMINDER: str = "off"
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
    def LLM_INCLUDE_SECTIONS(self) -> list[str]:
        """Order-sensitive list of prompt sections to include.

        Read from ZRB_LLM_INCLUDE_SECTIONS (comma-separated). Falls back to
        the default in DEFAULT_LLM_INCLUDE_SECTIONS.
        """
        raw = get_env(
            "LLM_INCLUDE_SECTIONS",
            self.DEFAULT_LLM_INCLUDE_SECTIONS,
            self.ENV_PREFIX,
        )
        return [s.strip() for s in raw.split(",") if s.strip()]

    @LLM_INCLUDE_SECTIONS.setter
    def LLM_INCLUDE_SECTIONS(self, value: list[str] | str):
        if isinstance(value, list):
            value = ",".join(value)
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_SECTIONS"] = value

    @property
    def LLM_INCLUDE_JOURNAL_REMINDER(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_INCLUDE_JOURNAL_REMINDER",
                self.DEFAULT_LLM_INCLUDE_JOURNAL_REMINDER,
                self.ENV_PREFIX,
            )
        )

    @LLM_INCLUDE_JOURNAL_REMINDER.setter
    def LLM_INCLUDE_JOURNAL_REMINDER(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_INCLUDE_JOURNAL_REMINDER"] = (
            "on" if value else "off"
        )
