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
        # Per-tool rules live in tool docstrings, which pydantic-ai ships with
        # the schema on every request. The skill catalogue is injected into
        # workflow via {CORE_SKILLS}/{AVAILABLE_SKILLS}/{PREACTIVATED_SKILLS}.
        self.DEFAULT_LLM_INCLUDE_SECTIONS: str = (
            "persona,workflow,examples,system_context,project_context"
        )
        # Prompt preset (ADR-0049): "full", "lean" or "minimal"; "auto" resolves
        # one from the model id, falling back to "full". A preset binds a section
        # list, a phrasing variant (workflow.lean.md over workflow.md) and a tool
        # surface. zrb makes no capability guess from a model *family* name —
        # only from a declared parameter count or a vendor small-tier label.
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
            "Prompt profile — a preset binding which sections compose, how "
            "they are phrased, and which tools register. The names order "
            "themselves by how much the model is asked to hold at once:\n"
            "- 'full': the whole rulebook and all 21 tools, on the base "
            "prompts.\n"
            "- 'lean': every section and every tool, on a lighter rulebook "
            "plus worked examples, for small models (~5-14B).\n"
            "- 'minimal': a three-section prompt and a 10-tool surface, for "
            "very small models (~3B). No skills, sub-agents, web, todos or "
            "project-doc reading.\n"
            "- 'auto' (default): resolved from the model id — a declared size "
            "of 4B or less selects 'minimal', 5-14B or a vendor small-tier "
            "label selects 'lean', otherwise 'full'. Override per model with "
            "register_model_profile().\n\n"
            "Setting LLM_INCLUDE_SECTIONS explicitly overrides a preset's "
            "section list.\n\n"
        ),
    )
