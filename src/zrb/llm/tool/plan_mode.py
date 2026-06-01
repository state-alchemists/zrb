"""Plan-mode tools: enter a read-only discovery phase, then present a plan.

In PLAN mode the execution gate (``agent/common.py``) denies edit, execute, and
delegate tools via ``PLAN_MODE_POLICY``, leaving reads, research, and harness
controls available. ``EnterPlanMode`` / ``ExitPlanMode`` are tagged ``META`` so
they are always permitted — you must be able to leave the mode you entered.

The mode lives in a ``ContextVar`` (``current_agent_mode``), so sub-agents
inherit it exactly like the active worktree.
"""

from __future__ import annotations

from zrb.llm.permission import Capability, tag
from zrb.llm.permission.state import AgentMode, current_agent_mode
from zrb.llm.tool.wrapper import tool_safe_async


@tool_safe_async
async def enter_plan_mode(reason: str = "") -> str:
    """
    Switch to read-only PLAN mode for safe discovery.

    While in PLAN mode, file edits, shell commands, and delegation are blocked;
    reading, searching, analysis, and web research stay available. Use it to
    investigate before any risky or multi-file change, then call ExitPlanMode
    to present your plan for approval before executing.

    `reason` optionally records why you entered plan mode.
    """
    current_agent_mode.set(AgentMode.PLAN)
    suffix = f" Reason: {reason}" if reason else ""
    return (
        "Entered PLAN mode (read-only): edits, shell, and delegation are "
        "blocked. Investigate, then call ExitPlanMode with your concrete plan "
        f"to resume normal execution.{suffix}"
    )


@tool_safe_async
async def exit_plan_mode(plan: str) -> str:
    """
    Leave PLAN mode and present the completed plan so execution can begin.

    `plan` is the concrete, ordered change list (what changes land where and
    why) shown to the user for approval before any edits are made.
    """
    current_agent_mode.set(AgentMode.DEFAULT)
    return (
        "Exited PLAN mode; resuming DEFAULT mode. Proposed plan:\n\n"
        f"{plan}"
    )


enter_plan_mode.__name__ = "EnterPlanMode"
exit_plan_mode.__name__ = "ExitPlanMode"
tag(enter_plan_mode, Capability.META)
tag(exit_plan_mode, Capability.META)
