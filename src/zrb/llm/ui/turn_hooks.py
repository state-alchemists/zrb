"""The hook manager a UI fires a turn's hooks through."""

from __future__ import annotations

from typing import Any

from zrb.llm.hook.manager import HookManager, hook_manager


def get_turn_hook_manager(llm_task: Any) -> HookManager:
    """The manager the turns of *llm_task* run with: a chat task's active
    one, else the task's own (the inner LLMTask a chat UI holds is built with
    it), else the process-wide one."""
    return (
        getattr(llm_task, "active_hook_manager", None)
        or getattr(llm_task, "hook_manager", None)
        or hook_manager
    )
