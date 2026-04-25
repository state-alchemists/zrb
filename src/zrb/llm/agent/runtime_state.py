"""Ambient state for an agent run — UI, tool confirmation, YOLO, approval channel.

These are set once by `run_agent` at the start of a turn and read by sub-agents,
delegate tools, and UI callbacks that don't receive them as explicit arguments.

The underlying `ContextVar`s live at their historical locations so that
`token = var.set(...)` / `var.reset(token)` patterns in `run_agent` keep working
without change. This module adds typed getters so callers don't reach into
`run_agent` or `approval_channel` just to read ambient state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.agent.run_agent import (
    AnyToolConfirmation,
    current_tool_confirmation,
    current_ui,
    current_yolo,
)
from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    current_approval_channel,
)

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import UIProtocol


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


__all__ = [
    "current_ui",
    "current_tool_confirmation",
    "current_yolo",
    "current_approval_channel",
    "get_current_ui",
    "get_current_tool_confirmation",
    "get_current_yolo",
    "get_current_approval_channel",
]
