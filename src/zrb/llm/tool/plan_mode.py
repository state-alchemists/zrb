"""Plan-mode tools: enter a read-only discovery phase, then present a plan.

In PLAN mode the execution gate (``agent/common.py``) denies edit, execute, and
delegate tools via ``PLAN_MODE_POLICY``, leaving reads, research, and harness
controls available.

The mode lives in a **mutable** ``AgentModeState`` (see ``state.py``) so that
pydantic-ai's per-tool task snapshots all see the same value.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from zrb.llm.permission import Capability, tag
from zrb.llm.permission.state import AgentMode, set_current_agent_mode
from zrb.llm.tool.wrapper import tool_safe_async


@tool_safe_async
async def enter_plan_mode(
    reason: Annotated[
        str, Field(description="Optionally records why you entered plan mode.")
    ] = "",
) -> str:
    """
    Switch to read-only PLAN mode for safe discovery.

    While in PLAN mode, file edits, shell commands, and delegation are blocked;
    reading, searching, analysis, and web research stay available.
    """
    set_current_agent_mode(AgentMode.PLAN)
    suffix = f" Reason: {reason}" if reason else ""
    return (
        "Entered PLAN mode (read-only): edits, shell, and delegation are "
        "blocked. Investigate, then call ExitPlanMode with your concrete plan "
        f"to resume normal execution.{suffix}"
    )


@tool_safe_async
async def exit_plan_mode(
    plan: Annotated[
        str,
        Field(
            description=(
                "The concrete, ordered change list (what changes land where "
                "and why), shown to the user for approval before any edits "
                "are made."
            )
        ),
    ],
) -> str:
    """
    Leave PLAN mode and present the completed plan so execution can begin.
    """
    set_current_agent_mode(AgentMode.BUILD)
    return "Exited PLAN mode; resuming BUILD mode. Proposed plan:\n\n" f"{plan}"


enter_plan_mode.__name__ = "EnterPlanMode"
exit_plan_mode.__name__ = "ExitPlanMode"
tag(enter_plan_mode, Capability.META)
tag(exit_plan_mode, Capability.META)
