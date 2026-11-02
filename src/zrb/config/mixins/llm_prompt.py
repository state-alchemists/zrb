"""LLM prompt config: prompt dirs, tool-call visibility, include-sections list."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField, comma_join, comma_list, on_off
from zrb.util.string.conversion import to_boolean


def _include_sections_serialize(value: list[str] | str) -> str:
    return ",".join(value) if isinstance(value, list) else value


class LLMPromptMixin:
    if TYPE_CHECKING:
        # Attributes supplied by sibling mixins on the composed Config class.
        ENV_PREFIX: str  # FoundationMixin
        ROOT_GROUP_NAME: str  # FoundationMixin

    def __init__(self):
        self.DEFAULT_LLM_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_BASE_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_SHOW_TOOL_CALL_DETAIL: str = "off"
        self.DEFAULT_LLM_SHOW_TOOL_CALL_RESULT: str = "off"
        # Keep file-backed rule sections before runtime context sections.
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
        # On: a project's rules are worth the tokens. A listed path is only a
        # promise the model will read it, and a missed convention costs a
        # correction later. Bounded by the byte budget below.
        self.DEFAULT_LLM_INJECT_PROJECT_INSTRUCTIONS: str = "on"
        # 24KB: room for a substantial AGENTS.md, small enough that a runaway
        # one cannot crowd out the conversation.
        self.DEFAULT_LLM_PROJECT_INSTRUCTIONS_MAX_BYTES: str = "24000"
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

    LLM_INJECT_PROJECT_INSTRUCTIONS = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "When on, the project's AGENTS.md / CLAUDE.md / GEMINI.md content is "
            "inlined into the system prompt instead of only being listed for the "
            "model to read.\n\n"
            "The nearest file to the working directory is inlined first and the "
            "byte budget is spent on it before broader ones. On by default: a "
            "listed path is a promise the model may not keep, and a convention "
            "missed on the first edit costs a correction later. Turn it off when "
            "the files are large enough that the prompt should only point at them."
        ),
    )

    LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = EnvField(
        int,
        doc=(
            "Byte budget for inlined project instructions (see "
            "LLM_INJECT_PROJECT_INSTRUCTIONS). The most specific file is "
            "truncated to fit rather than dropped; broader files that do not fit "
            "stay listed by path only."
        ),
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
            "Prompt profile: 'minimal', 'standard', 'capable', or 'auto' "
            "(default). It selects profile.<name>.md; 'minimal' additionally "
            "registers no delegate (sub-agent) tools. 'auto' derives one from "
            "the model id: "
            "a declared size of 4B or less selects 'minimal', 5-14B 'standard', "
            "above 14B 'capable'; an id declaring nothing falls back to "
            "'standard'. Set a profile name to skip the derivation."
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
