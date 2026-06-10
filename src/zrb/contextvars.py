"""Index of every `ContextVar` in zrb.

This is the one file to open when you want to know what ambient state the
runtime propagates. It re-exports wrappers (and the underlying `ContextVar`s)
from three homes that keep bounded-context ownership of their state:

* `zrb.context.any_context`   - the per-task execution Context (`current_ctx`)
* `zrb.llm.agent.run.runtime_state` - agent-run ambient state (UI, YOLO, approval, ...)
* `zrb.llm.permission.state`  - permission policy + agent mode (plan/default)
* `zrb.llm.sandbox.state`     - sandbox policy (filesystem containment)
* `zrb.llm.tool.ambient_state`  - tool-scoped ambient state (worktree, session)

Nothing here owns state. This module exists purely as a discoverable registry
so contributors can answer "what ContextVars exist?" without grepping.

When you add, remove, or rename a `ContextVar`, also update:
  - docs/advanced-topics/maintainer-guide.md  (Context Propagation Internals — the count and per-layer table)
  - docs/advanced-topics/architecture.md      (Implicit State via ContextVars — the count)

(AGENTS.md just points here, so it doesn't need updating.)
"""

from __future__ import annotations

# --- Task execution context ---
from zrb.context.any_context import current_ctx, get_current_ctx, zrb_print

# --- Agent runtime state ---
from zrb.llm.agent.run.runtime_state import (
    current_approval_channel,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_approval_channel,
    get_current_tool_confirmation,
    get_current_ui,
    get_current_yolo,
)

# --- Permission state (policy + agent mode) ---
from zrb.llm.permission.state import (
    current_agent_mode,
    current_permission_policy,
    get_current_agent_mode,
    get_current_permission_policy,
    set_current_agent_mode,
    set_current_permission_policy,
)

# --- Sandbox state (filesystem containment policy) ---
from zrb.llm.sandbox.state import (
    current_sandbox_policy,
    get_current_sandbox_policy,
    set_current_sandbox_policy,
)

# --- Tool ambient state ---
from zrb.llm.tool.ambient_state import (
    active_worktree,
    get_active_worktree,
    get_current_tool_session,
    get_interactive_mode,
    interactive_mode,
    set_active_worktree,
    set_current_tool_session,
    set_interactive_mode,
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
    # Permission state
    "current_permission_policy",
    "current_agent_mode",
    "get_current_permission_policy",
    "set_current_permission_policy",
    "get_current_agent_mode",
    "set_current_agent_mode",
    # Sandbox state
    "current_sandbox_policy",
    "get_current_sandbox_policy",
    "set_current_sandbox_policy",
    # Tool ambient state
    "active_worktree",
    "get_active_worktree",
    "set_active_worktree",
    "get_current_tool_session",
    "set_current_tool_session",
    "interactive_mode",
    "get_interactive_mode",
    "set_interactive_mode",
]
