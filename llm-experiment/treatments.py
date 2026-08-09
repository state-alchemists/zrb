"""Prompt arms under test.

zrb arms are composed through the real ``PromptManager``, not a copy of the
markdown, so an arm always reflects what zrb would actually send. opencode arms
are read from a checkout of that repo.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from probes import CANARY_RULE

OPENCODE_PROMPTS = (
    Path(os.environ.get("OPENCODE_DIR", Path.home() / "opencode"))
    / "packages/opencode/src/session/prompt"
)


def _compose(profile: str, sections: list[str] | None = None) -> str:
    """Compose a zrb prompt exactly as the shipped code would."""
    # lazy: zrb reads CFG at import; the env has to be set before it binds
    os.environ["ZRB_LLM_PROFILE"] = profile
    os.environ["ZRB_LLM_JOURNAL_ENABLED"] = "false"
    from zrb.llm.prompt.manager import PromptManager

    return PromptManager(include_sections=sections).compose_prompt()(MagicMock())


def zrb_arms() -> dict[str, str]:
    """X1 (preset ladder) and X4 (section ablation)."""
    full_sections = [
        "persona",
        "workflow",
        "examples",
        "system_context",
        "project_context",
    ]
    return {
        "zrb-full": _compose("full"),
        "zrb-minimal": _compose("minimal"),
        "zrb-full-no-persona": _compose(
            "full", [s for s in full_sections if s != "persona"]
        ),
        "zrb-full-no-examples": _compose(
            "full", [s for s in full_sections if s != "examples"]
        ),
    }


def opencode_arms() -> dict[str, str]:
    """X3 (family portability). Missing files are skipped, not faked."""
    arms = {}
    for name in ("anthropic", "gemini", "kimi"):
        path = OPENCODE_PROMPTS / f"{name}.txt"
        if path.exists():
            arms[f"opencode-{name}"] = path.read_text()
    return arms


def canary_arms() -> dict[str, str]:
    """X2 (rule position): one extra rule, three places in the same prompt.

    Inserted at line granularity into the composed ``full`` prompt so the three
    arms differ in nothing but the index of a single line.
    """
    base = _compose("full")
    lines = base.splitlines()
    rule = ["", CANARY_RULE, ""]
    positions = {
        "canary-start": 1,
        "canary-middle": len(lines) // 2,
        "canary-end": len(lines),
    }
    return {
        name: "\n".join(lines[:i] + rule + lines[i:]) for name, i in positions.items()
    }


def all_arms() -> dict[str, str]:
    return {**zrb_arms(), **opencode_arms(), **canary_arms()}
