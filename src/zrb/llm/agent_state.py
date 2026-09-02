"""Ambient state for an agent run — UI, tool confirmation, YOLO, approval channel.

These are set once by `run_agent` (`agent/run/runner.py`) at the start of a
turn and read by sub-agents, delegate tools, and UI callbacks that don't
receive them as explicit arguments.

Deliberately NOT inside the `zrb.llm.agent` package, even though `run_agent`
is this module's only writer: importing `zrb.llm.agent` (for `create_agent`/
`run_agent`) eagerly loads the whole agent-construction and run-loop
machinery, and a long list of otherwise-unrelated leaf modules — `tool/ask.py`,
`tool/plan.py`, `tool/shell.py`, `tool/web.py`, `tool/delegate.py`,
`tool/file_observation.py`, `ui/base/ui.py` — need nothing from that
machinery, only a `ContextVar` getter. When this module lived at
`agent/run/runtime_state.py`, importing any of those forced `zrb.llm.agent`'s
package `__init__` to run first (Python imports parent packages before
submodules), which is what made `live_context.py` and `agent/run/setup.py`
genuinely circular: each needed one of those same leaf modules, which by then
needed `zrb.llm.agent` back. Moving the state itself out of the `agent`
package — rather than deferring more of the imports that reach it — removes
that cycle at its source instead of routing around it again. See
`test/architecture/test_circular_import_allowlist.py`'s allowlist comment for
the closure-walk evidence.

Callers outside `zrb.llm.agent.run` should use the typed getters below rather
than the raw vars.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias

from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    current_approval_channel,
)

if TYPE_CHECKING:
    from pydantic_ai.models import Model

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
# The per-session small/multimodal model override a UI's `/model small ...` /
# `/model multimodal ...` set (`BaseUI.small_model`/`.multimodal_model`), or
# None when unset. `run_agent` binds these from the UI it was given; a nested
# helper reads the getter below and falls back to
# `resolve_configured_small_model()`/`resolve_configured_multimodal_model()`
# (`zrb.llm.config.model_resolver`) when unset — the same "task override,
# else CFG" shape `model` itself already uses. Existing per-run isolation for
# free: a ContextVar is only visible within the `asyncio.Task` that set it (and
# its children), so two concurrent chat sessions in the same process never see
# each other's `/model small ...` choice.
current_small_model: ContextVar["str | Model | None"] = ContextVar(
    "current_small_model", default=None
)
current_multimodal_model: ContextVar["str | Model | None"] = ContextVar(
    "current_multimodal_model", default=None
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
    `current_agent_run_scope`'s docstring above)."""
    return current_agent_run_scope.get()


def get_current_small_model() -> "str | Model | None":
    """Return the current run's small-model override, or None if unset —
    callers fall back to `resolve_configured_small_model()`."""
    return current_small_model.get()


def get_current_multimodal_model() -> "str | Model | None":
    """Return the current run's multimodal-model override, or None if unset
    — callers fall back to `resolve_configured_multimodal_model()`."""
    return current_multimodal_model.get()


__all__ = [
    "current_ui",
    "current_tool_confirmation",
    "current_yolo",
    "current_approval_channel",
    "current_hook_manager",
    "current_agent_run_scope",
    "current_small_model",
    "current_multimodal_model",
    "get_current_ui",
    "get_current_tool_confirmation",
    "get_current_yolo",
    "get_current_approval_channel",
    "get_current_hook_manager",
    "get_current_agent_run_scope",
    "get_current_small_model",
    "get_current_multimodal_model",
]
