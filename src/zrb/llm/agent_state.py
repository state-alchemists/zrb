"""Ambient state for an agent run — UI, tool confirmation, YOLO, approval channel.

Set by `run_agent` (`agent/run/runner.py`) at the start of a turn; read by
sub-agents, delegate tools and UI callbacks that don't receive them as
arguments.

Lives outside `zrb.llm.agent` so leaf modules (`tool/ask.py`, `tool/shell.py`,
`ui/base/ui.py`, ...) can read it without loading that package's `__init__`,
which would be circular (see `test/architecture/test_circular_import_allowlist.py`).
Outside `zrb.llm.agent.run`, use the typed getters rather than the raw vars.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, TypeAlias

from zrb.llm.approval.approval_channel import current_approval_channel

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from zrb.llm.agent.types import ToolApproved, ToolCallPart, ToolDenied
    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.config.limiter import LLMLimiter
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.tool_call.handler import ToolCallHandler
    from zrb.llm.ui.any_ui import AnyUI

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

current_ui: ContextVar["AnyUI | None"] = ContextVar("current_ui", default=None)
current_tool_confirmation: ContextVar[AnyToolConfirmation] = ContextVar(
    "current_tool_confirmation", default=None
)
current_yolo: ContextVar[bool] = ContextVar("current_yolo", default=False)
# The hook manager active for the current run. Read by nested tools (e.g. the
# delegate tool fires SubagentStart/Stop on the parent run's manager).
current_hook_manager: ContextVar["HookManager | None"] = ContextVar(
    "current_hook_manager", default=None
)
# Identifies "this agent run" to tools that keep per-conversation state
# (file_observation.py). Stable across turns of a top-level conversation (its
# session name); a delegated sub-agent gets a fresh uuid4, since it has not
# seen what its parent observed.
current_agent_run_scope: ContextVar[str] = ContextVar(
    "current_agent_run_scope", default=""
)
# The session's `/model small ...` / `/model multimodal ...` override, or None;
# helpers fall back to `resolve_configured_small_model()`/`..._multimodal_model()`.
current_small_model: ContextVar["str | Model | None"] = ContextVar(
    "current_small_model", default=None
)
current_multimodal_model: ContextVar["str | Model | None"] = ContextVar(
    "current_multimodal_model", default=None
)
# The main model this run uses (reflecting `/model` or `--model`).
# `resolve_configured_small_model` falls back to it before `CFG.LLM_MODEL`,
# whose provider may lack credentials.
current_model: ContextVar["str | Model | None"] = ContextVar(
    "current_model", default=None
)
# The current run's limiter, for tools that make model calls of their own.
current_llm_limiter: ContextVar["LLMLimiter | None"] = ContextVar(
    "current_llm_limiter", default=None
)


def get_current_ui() -> "AnyUI | None":
    """Return the UI active for the current agent run, or None if unset."""
    return current_ui.get()


def get_current_tool_confirmation() -> AnyToolConfirmation:
    """Return the tool-confirmation callback active for the current agent run."""
    return current_tool_confirmation.get()


def get_current_yolo() -> bool:
    """Return the YOLO (auto-approve) flag for the current agent run."""
    return current_yolo.get()


def get_current_approval_channel() -> "AnyApprovalChannel | None":
    """Return the approval channel active for the current agent run, or None."""
    return current_approval_channel.get()


def get_current_llm_limiter() -> "LLMLimiter | None":
    """Return the limiter active for the current agent run, or None."""
    return current_llm_limiter.get()


def get_current_hook_manager() -> "HookManager | None":
    """Return the hook manager active for the current agent run, or None."""
    return current_hook_manager.get()


def get_current_agent_run_scope() -> str:
    """Return the id identifying the current agent run."""
    return current_agent_run_scope.get()


def get_current_small_model() -> "str | Model | None":
    """Return the current run's small-model override, or None if unset."""
    return current_small_model.get()


def get_current_model() -> "str | Model | None":
    """Return the main model of the current agent run, or None outside a run."""
    return current_model.get()


def get_current_multimodal_model() -> "str | Model | None":
    """Return the current run's multimodal-model override, or None if unset."""
    return current_multimodal_model.get()


__all__ = [
    "current_ui",
    "current_tool_confirmation",
    "current_yolo",
    "current_approval_channel",
    "current_hook_manager",
    "current_llm_limiter",
    "current_agent_run_scope",
    "current_small_model",
    "current_multimodal_model",
    "current_model",
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
]
