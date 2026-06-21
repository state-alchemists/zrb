"""LLM prompt config: prompt dirs, tool-call visibility, include-sections list."""

from __future__ import annotations

import os

from zrb.config.env_field import EnvField, comma_list, on_off
from zrb.util.string.conversion import to_boolean


def _include_sections_serialize(value: list[str] | str) -> str:
    return ",".join(value) if isinstance(value, list) else value


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

    LLM_PROMPT_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_PROMPT_DIR
            or os.path.join(f".{cfg.ROOT_GROUP_NAME}", "llm", "prompt")
        ),
        doc="Directory for project-level prompt override files (.md or .py).",
    )

    LLM_BASE_PROMPT_DIR = EnvField(
        str,
        doc="Base directory containing the built-in prompt templates. Overrides the package default.",
    )

    LLM_SHOW_TOOL_CALL_DETAIL = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Show tool call arguments in the UI alongside the tool name.",
    )

    LLM_SHOW_TOOL_CALL_RESULT = EnvField(
        to_boolean, serialize=on_off, doc="Show the full tool call result in the UI."
    )

    LLM_INCLUDE_SECTIONS = EnvField(
        comma_list,
        serialize=_include_sections_serialize,
        doc=(
            "Order-sensitive list of prompt sections to include.\n\n"
            "Read from ZRB_LLM_INCLUDE_SECTIONS (comma-separated). Falls back "
            "to the default in DEFAULT_LLM_INCLUDE_SECTIONS."
        ),
    )

    LLM_INCLUDE_JOURNAL_REMINDER = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Inject a journaling reminder into the system prompt at each turn (separate from journal_mandate section).",
    )
