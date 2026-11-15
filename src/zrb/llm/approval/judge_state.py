"""The shell judge's session switch; mirrors ``zrb.llm.sandbox.state``."""

from __future__ import annotations

from zrb.config.config import CFG
from zrb.llm.shared.agent_state import get_current_ui


def judge_override_of(ui: object) -> bool | None:
    """A UI's `/judge` choice, or None when it never made one.

    `getattr` plus the ``isinstance`` filter rather than a plain attribute
    read, for the reason the sandbox switch has: a headless UI need not carry
    the tools role, and a stand-in's auto-created attribute is a mock, not a
    decision.
    """
    value = getattr(getattr(ui, "tools", None), "judge_override", None)
    return value if isinstance(value, bool) else None


def is_shell_judge_enabled_for(ui: object) -> bool:
    """Whether the judge is consulted for the session behind `ui`.

    The session's switch first, then the deployment's setting. Only the
    *consultation* is here: `LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED` — the one
    that lets a `safe` verdict skip the prompt — stays a deployment decision,
    because a switch that removes a person from the loop is not something to
    put one keystroke away.
    """
    override = judge_override_of(ui)
    if override is not None:
        return override
    return CFG.LLM_SHELL_JUDGE_ENABLED


def is_shell_judge_enabled() -> bool:
    """The answer for the run in progress, or the deployment's when there is none."""
    return is_shell_judge_enabled_for(get_current_ui())
