"""Ambient permission state: the in-force policy and agent mode."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generator

from zrb.llm.permission.policy import PLAN_MODE_POLICY, PermissionPolicy
from zrb.util.contextvar_scope import scoped


class AgentMode(str, Enum):
    BUILD = "build"
    PLAN = "plan"


@dataclass
class AgentModeState:
    """Mutable mode holder.

    pydantic-ai runs each tool call in its own task, which copies the
    ContextVar map; mutating ``.mode`` reaches every copy, ``set()`` would not.
    """

    mode: AgentMode = AgentMode.BUILD


current_permission_policy: ContextVar[PermissionPolicy | None] = ContextVar(
    "current_permission_policy", default=None
)
current_agent_mode: ContextVar[AgentModeState] = ContextVar(
    "current_agent_mode", default=AgentModeState()
)


def get_current_permission_policy() -> "PermissionPolicy | None":
    return current_permission_policy.get()


@contextmanager
def permission_policy(policy: "PermissionPolicy | None") -> Generator[None]:
    """Scope `policy` as the in-force permission policy for the `with` block."""
    with scoped(current_permission_policy, policy):
        yield


def get_current_agent_mode() -> AgentMode:
    return current_agent_mode.get().mode


def set_current_agent_mode(mode: AgentMode) -> None:
    """Set the mode on the run's shared ``AgentModeState``."""
    current_agent_mode.get().mode = mode


def enter_agent_mode_scope() -> "tuple[Any, AgentModeState]":
    """Bind a run-local ``AgentModeState`` inheriting the current mode.

    Keeps concurrent runs from sharing the import-time default instance.
    Returns ``(token, parent_state)`` for ``exit_agent_mode_scope``.
    """
    parent_state = current_agent_mode.get()
    run_state = AgentModeState(mode=parent_state.mode)
    token = current_agent_mode.set(run_state)
    return token, parent_state


def exit_agent_mode_scope(token: "Any", parent_state: AgentModeState) -> None:
    """Undo ``enter_agent_mode_scope``, copying the run's final mode to the caller.

    Keeps an in-run plan-mode switch sticky across UI turns.
    """
    run_state = current_agent_mode.get()
    parent_state.mode = run_state.mode
    current_agent_mode.reset(token)


def get_effective_policy() -> "PermissionPolicy | None":
    """``PLAN_MODE_POLICY`` in plan mode, else the explicit policy (or ``None``)."""
    if current_agent_mode.get().mode == AgentMode.PLAN:
        return PLAN_MODE_POLICY
    return current_permission_policy.get()
