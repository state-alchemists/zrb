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
        # The seven prompt sections are deliberately fixed and ordered: the five
        # file-backed rule sections, then the two runtime-fact sections
        # (system_context renders the environment, project_context the project
        # docs discovered near the working directory).
        self.DEFAULT_LLM_INCLUDE_SECTIONS: str = (
            "persona,principle,workflow,example,profile,system_context,project_context"
        )
        self.DEFAULT_LLM_PROFILE: str = "auto"
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
        doc="Order-sensitive list of prompt sections to include (comma-separated).",
    )

    LLM_PROFILE = EnvField(
        str,
        doc=(
            "Prompt profile: 'minimal', 'standard' (default), or 'capable'. "
            "It selects profile.<name>.md; 'minimal' additionally registers no "
            "delegate (sub-agent) tools. 'auto' derives one from the model id: "
            "a declared size of 4B or less selects 'minimal', 5-14B 'standard', "
            "above 14B 'capable'; an id declaring nothing falls back to "
            "'standard'. Override per model with ZRB_LLM_PROFILE.\n"
        ),
    )
