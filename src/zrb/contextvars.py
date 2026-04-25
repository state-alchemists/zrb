"""Index of every `ContextVar` in zrb.

This is the one file to open when you want to know what ambient state the
runtime propagates. It re-exports wrappers (and the underlying `ContextVar`s)
from three homes that keep bounded-context ownership of their state:

* `zrb.context.any_context`   - the per-task execution Context (`current_ctx`)
* `zrb.llm.agent.runtime_state` - agent-run ambient state (UI, YOLO, approval, ...)
* `zrb.llm.tool.ambient_state`  - tool-scoped ambient state (worktree, session)

Nothing here owns state. This module exists purely as a discoverable registry
so contributors can answer "what ContextVars exist?" without grepping.
"""

from __future__ import annotations

# --- Task execution context ---
from zrb.context.any_context import current_ctx, get_current_ctx, zrb_print

# --- Agent runtime state ---
from zrb.llm.agent.runtime_state import (
    current_approval_channel,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_approval_channel,
    get_current_tool_confirmation,
    get_current_ui,
    get_current_yolo,
)

# --- Tool ambient state ---
from zrb.llm.tool.ambient_state import (
    active_worktree,
    get_active_worktree,
    get_current_tool_session,
    set_active_worktree,
    set_current_tool_session,
)

__all__ = [
    # Task execution context
    "current_ctx",
    "get_current_ctx",
    "zrb_print",
    # Agent runtime state
    "current_ui",
    "current_tool_confirmation",
    "current_yolo",
    "current_approval_channel",
    "get_current_ui",
    "get_current_tool_confirmation",
    "get_current_yolo",
    "get_current_approval_channel",
    # Tool ambient state
    "active_worktree",
    "get_active_worktree",
    "set_active_worktree",
    "get_current_tool_session",
    "set_current_tool_session",
]
