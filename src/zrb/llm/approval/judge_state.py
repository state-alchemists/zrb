"""The shell judge's session switches; mirrors ``zrb.llm.sandbox.state``."""

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

    The session's switch first, then the deployment's setting. Consultation
    only: the half that lets a `safe` verdict skip the prompt has its own
    answer in `is_shell_judge_auto_approve_enabled_for`.
    """
    override = judge_override_of(ui)
    if override is not None:
        return override
    return CFG.LLM_SHELL_JUDGE_ENABLED


def is_shell_judge_auto_approve_enabled_for(ui: object) -> bool:
    """Whether a `safe` verdict may skip the prompt for the session behind `ui`.

    The deployment's second setting, unless the session touched the switch
    itself: `/judge on` says "consult, and still ask", so it withdraws the auto
    half for that conversation even where the deployment granted it. Every
    keystroke can only move towards asking; a launch flag or the environment is
    the only way to the second grant. `--judge auto-approve` is that launch
    flag: it writes both settings for the run, so a session that never touched
    `/judge` keeps the answer it started with.

    Both settings are read because the second is meaningless without the first:
    a deployment that turned consultation off has no verdict to skip a prompt
    with, and a badge that said otherwise would be describing a grant nothing
    can use.
    """
    if judge_override_of(ui) is not None:
        return False
    return bool(CFG.LLM_SHELL_JUDGE_ENABLED and CFG.LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED)


def is_shell_judge_enabled() -> bool:
    """The answer for the run in progress, or the deployment's when there is none."""
    return is_shell_judge_enabled_for(get_current_ui())


def is_shell_judge_auto_approve_enabled() -> bool:
    """The answer for the run in progress, or the deployment's when there is none."""
    return is_shell_judge_auto_approve_enabled_for(get_current_ui())
