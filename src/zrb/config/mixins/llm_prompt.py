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
        # Each section is MECE (mutually exclusive in concern). Three carry
        # rules: persona=identity+response style, workflow=priority order + turn
        # sequence + skill catalogue + working loop + verify gate + recovery,
        # examples=demonstrations only. Two carry runtime facts:
        # system_context=stable facts (OS, CWD, model), project_context=
        # AGENTS.md/CLAUDE.md discovery.
        # There is no tool section: per-tool rules live in tool docstrings,
        # which pydantic-ai ships with the schema on every request.
        # The skill catalogue is injected into workflow via {CORE_SKILLS}/
        # {AVAILABLE_SKILLS}/{PREACTIVATED_SKILLS} placeholders, not a separate
        # section.
        self.DEFAULT_LLM_INCLUDE_SECTIONS: str = (
            "persona,workflow,examples,system_context,project_context"
        )
        # Prompt profile (ADR-0047): "terse" (base prompts) or "mini"
        # (base prompts plus worked examples, for small models); "auto" uses "terse"
        # unless a per-model profile is declared via register_model_profile().
        # zrb makes no capability guess from the model id. The profile selects
        # per-section phrasing variants (e.g. persona.mini.md over persona.md);
        # which sections appear is controlled solely by LLM_INCLUDE_SECTIONS.
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
            "Prompt profile controlling how each section is phrased:\n"
            "- 'terse': concise, principle-led — the base prompts.\n"
            "- 'mini': the same rules plus worked examples, for small "
            "models.\n"
            "- 'auto' (default): uses 'terse' unless a per-model profile has "
            "been declared via register_model_profile().\n\n"
            "The profile selects per-section phrasing variants (e.g. "
            "persona.mini.md, falling back to the base file) and toggles the "
            "examples section.\n\n"
        ),
    )
