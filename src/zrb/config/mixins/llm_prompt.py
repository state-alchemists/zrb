"""LLM prompt config: prompt dirs, tool-call visibility, include-sections list."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField, comma_join, comma_list, on_off
from zrb.util.string.conversion import to_boolean


def _include_sections_serialize(value: list[str] | str) -> str:
    return ",".join(value) if isinstance(value, list) else value


class ConfigLLMPrompt:
    if TYPE_CHECKING:
        # Attributes supplied by sibling mixins on the composed Config class.
        ENV_PREFIX: str  # FoundationMixin
        ROOT_GROUP_NAME: str  # FoundationMixin

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
        self.DEFAULT_LLM_PROMPT: str = ""
        self.DEFAULT_LLM_PROFILE: str = "auto"
        # The model-facing skill/agent catalogues are capped so a huge skill or
        # sub-agent fleet does not inflate every request; the overflow is reachable
        # on demand via SearchSkill / SearchAgent.
        self.DEFAULT_LLM_MAX_SKILLS_IN_CATALOG: str = "10"
        self.DEFAULT_LLM_MAX_AGENTS_IN_ROSTER: str = "10"
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

    LLM_PROMPT = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Default appended prompts (on top of the built-in sections), the env "
            "twin of `prompt_registry`. Comma-separated; set callables "
            "or longer content in zrb_init.py via `prompt_registry` instead."
        ),
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

    LLM_MAX_SKILLS_IN_CATALOG = EnvField(
        int,
        doc=(
            "How many model-invocable skills the prompt's skill catalogue lists "
            "before truncating with a pointer to SearchSkill. The full catalogue "
            "is always reachable on demand via SearchSkill, so this is a token-"
            "economy cap, not a hard limit. 0 or negative disables the cap, "
            "listing the whole catalogue."
        ),
    )

    LLM_MAX_AGENTS_IN_ROSTER = EnvField(
        int,
        doc=(
            "How many sub-agents the delegation tools' AVAILABLE AGENTS roster "
            "lists before truncating with a pointer to SearchAgent. The full "
            "roster is always reachable on demand via SearchAgent, so this is a "
            "token-economy cap, not a hard limit. 0 or negative disables the cap, "
            "listing the whole roster."
        ),
    )
