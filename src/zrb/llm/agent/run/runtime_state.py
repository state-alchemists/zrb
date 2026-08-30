"""Ambient state for an agent run — UI, tool confirmation, YOLO, approval channel.

These are set once by `run_agent` at the start of a turn and read by sub-agents,
delegate tools, and UI callbacks that don't receive them as explicit arguments.

This module OWNS the `ContextVar`s: `run_agent` (runner.py) binds them with
`token = var.set(...)` / `var.reset(token)` on entry, resets in `finally`, but
does not define them — `setup.py`, a module `runner.py` itself imports at the
top, needs these same vars, so defining them in `runner.py` would force every
such consumer into a lazy import to dodge the cycle. Defining them here instead
(a leaf module with no `zrb.llm.agent.run` imports of its own) lets both
`runner.py` and `setup.py` import them directly. Callers outside this package
should use the typed getters below rather than the raw vars.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias

from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    current_approval_channel,
)

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolApproved, ToolCallPart, ToolDenied
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.tool_call.handler import ToolCallHandler
    from zrb.llm.tool_call.ui_protocol import UIProtocol

    AnyToolConfirmation: TypeAlias = (
        Callable[
            [ToolCallPart],
            ToolApproved | ToolDenied | Awaitable[ToolApproved | ToolDenied],
        ]
        | ToolCallHandler
        | None
    )
else:
    AnyToolConfirmation: TypeAlias = Any

current_ui: ContextVar["UIProtocol | None"] = ContextVar("current_ui", default=None)
current_tool_confirmation: ContextVar[AnyToolConfirmation] = ContextVar(
    "current_tool_confirmation", default=None
)
current_yolo: ContextVar[bool] = ContextVar("current_yolo", default=False)
# The hook manager active for the current run. Read by nested tools (e.g. the
# delegate tool fires SubagentStart/Stop on the parent run's manager).
current_hook_manager: ContextVar["HookManager | None"] = ContextVar(
    "current_hook_manager", default=None
)
# Identifies "this specific agent run" to nested tools that need to track
# state per-conversation without bleeding across independent conversations —
# e.g. file_observation.py's read-before-overwrite tracking. Stable across
# turns of the same top-level conversation (the caller passes its session
# name). A delegated sub-agent run (delegate.py) deliberately passes nothing,
# taking the fresh-per-call default below instead: a sub-agent has its own
# empty message_history and hasn't seen what its parent or siblings
# observed, so it must not share their bucket — and delegate.py's own
# display-only agent_id is a 32-bit-truncated id, too collision-prone for a
# map this module never evicts, unlike the fresh full uuid4 below.
current_agent_run_scope: ContextVar[str] = ContextVar(
    "current_agent_run_scope", default=""
)


def get_current_ui() -> "UIProtocol | None":
    """Return the UI active for the current agent run, or None if unset."""
    return current_ui.get()


def get_current_tool_confirmation() -> AnyToolConfirmation:
    """Return the tool-confirmation callback active for the current agent run."""
    return current_tool_confirmation.get()


def get_current_yolo() -> bool:
    """Return the YOLO (auto-approve) flag for the current agent run."""
    return current_yolo.get()


def get_current_approval_channel() -> "ApprovalChannel | None":
    """Return the approval channel active for the current agent run, or None."""
    return current_approval_channel.get()


def get_current_hook_manager() -> "HookManager | None":
    """Return the hook manager active for the current agent run, or None."""
    return current_hook_manager.get()


def get_current_agent_run_scope() -> str:
    """Return the id identifying the current agent run (see
    `current_agent_run_scope`'s docstring in runner.py)."""
    return current_agent_run_scope.get()


__all__ = [
    "current_ui",
    "current_tool_confirmation",
    "current_yolo",
    "current_approval_channel",
    "current_hook_manager",
    "current_agent_run_scope",
    "get_current_ui",
    "get_current_tool_confirmation",
    "get_current_yolo",
    "get_current_approval_channel",
    "get_current_hook_manager",
    "get_current_agent_run_scope",
]
