"""Index of every `ContextVar` in zrb.

Re-exports wrappers (and the underlying `ContextVar`s) from the modules that
own them:

* `zrb.context.any_context`   - the per-task execution Context (`current_ctx`)
* `zrb.llm.agent_state` - agent-run ambient state (UI, YOLO, approval, ...)
* `zrb.llm.permission.state`  - permission policy + agent mode (plan/default)
* `zrb.llm.sandbox.state`     - sandbox policy (filesystem containment)
* `zrb.llm.tool.ambient_state`  - tool-scoped ambient state (worktree, session)

Nothing here owns state. When you add, remove, or rename a `ContextVar`, also
update:
  - docs/technical-specs/context-propagation.md  (the count and per-layer table)
  - docs/contributing/architecture.md      (Implicit State via ContextVars — the count)
"""

from __future__ import annotations

# --- Task execution context ---
from zrb.context.any_context import current_ctx, get_current_ctx, zrb_print

# --- Agent runtime state ---
from zrb.llm.agent_state import (
    current_agent_run_scope,
    current_approval_channel,
    current_hook_manager,
    current_llm_limiter,
    current_model,
    current_multimodal_model,
    current_small_model,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_agent_run_scope,
    get_current_approval_channel,
    get_current_hook_manager,
    get_current_llm_limiter,
    get_current_model,
    get_current_multimodal_model,
    get_current_small_model,
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
    permission_policy,
    set_current_agent_mode,
)

# --- Sandbox state (filesystem containment policy) ---
from zrb.llm.sandbox.state import (
    current_sandbox_policy,
    get_current_sandbox_policy,
    sandbox_policy,
)

# --- Tool ambient state ---
from zrb.llm.tool.ambient_state import (
    active_worktree,
    current_chat_session_id,
    get_active_worktree,
    get_current_chat_session_id,
    get_current_context_session,
    get_current_tool_session,
    get_input_provenance,
    get_interactive_mode,
    get_session_ownership_key,
    input_provenance,
    interactive_mode,
    set_active_worktree,
    set_current_session,
    set_current_tool_session,
    set_input_provenance,
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
    "current_hook_manager",
    "current_llm_limiter",
    "current_agent_run_scope",
    "current_small_model",
    "current_model",
    "current_multimodal_model",
    "get_current_ui",
    "get_current_tool_confirmation",
    "get_current_yolo",
    "get_current_approval_channel",
    "get_current_hook_manager",
    "get_current_llm_limiter",
    "get_current_agent_run_scope",
    "get_current_small_model",
    "get_current_model",
    "get_current_multimodal_model",
    # Permission state
    "current_permission_policy",
    "current_agent_mode",
    "get_current_permission_policy",
    "permission_policy",
    "get_current_agent_mode",
    "set_current_agent_mode",
    # Sandbox state
    "current_sandbox_policy",
    "get_current_sandbox_policy",
    "sandbox_policy",
    # Tool ambient state
    "active_worktree",
    "get_active_worktree",
    "set_active_worktree",
    "get_current_tool_session",
    "set_current_tool_session",
    "get_current_context_session",
    "set_current_session",
    "input_provenance",
    "get_input_provenance",
    "set_input_provenance",
    "interactive_mode",
    "get_interactive_mode",
    "set_interactive_mode",
    "current_chat_session_id",
    "get_current_chat_session_id",
    "get_session_ownership_key",
]
