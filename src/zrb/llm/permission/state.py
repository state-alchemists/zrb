"""Ambient permission state — the in-force policy and agent mode.

``current_agent_mode`` holds a **mutable** ``AgentModeState`` so a mode change
made inside one per-tool-call task is visible to every later one (see
``AgentModeState``).
"""

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
    """Mutable holder shared across tasks via a ``ContextVar``.

    pydantic-ai's ``asyncio.create_task`` (one per tool call) copies the
    current ``ContextVar`` *map*, but stores references to the same objects.
    Mutating ``.mode`` on this instance is visible in every task's context
    snapshot, whereas ``ContextVar.set()`` on an immutable value would only
    affect the calling task's copy.
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
    """Scope `policy` as the in-force permission policy for the `with` block.

    Always resets on exit, including on exception, so a policy set here can
    never leak into a later run sharing the same context.
    """
    with scoped(current_permission_policy, policy):
        yield


def get_current_agent_mode() -> AgentMode:
    return current_agent_mode.get().mode


def set_current_agent_mode(mode: AgentMode) -> None:
    """Set agent mode on the current run's mutable state so every task sees it.

    Mutates the run-local ``AgentModeState`` that ``enter_agent_mode_scope``
    bound, so ``EnterPlanMode`` / ``ExitPlanMode`` reach every per-tool-call
    task spawned afterwards.
    """
    current_agent_mode.get().mode = mode


def enter_agent_mode_scope() -> "tuple[Any, AgentModeState]":
    """Bind a fresh, run-local ``AgentModeState`` that inherits the current mode.

    Isolates concurrent runs (web chat sessions, MultiUI children, parallel
    sub-agents), which would otherwise all mutate the one import-time default
    instance and clobber each other's plan/build mode.

    Returns ``(token, parent_state)`` for ``exit_agent_mode_scope``.
    """
    parent_state = current_agent_mode.get()
    run_state = AgentModeState(mode=parent_state.mode)
    token = current_agent_mode.set(run_state)
    return token, parent_state


def exit_agent_mode_scope(token: "Any", parent_state: AgentModeState) -> None:
    """Tear down ``enter_agent_mode_scope``, propagating the final mode upward.

    The run's final mode is written back to the caller's state so an in-run
    ``EnterPlanMode`` / ``ExitPlanMode`` persists for the caller (e.g. the UI
    reads it back after the run to keep ``/plan`` sticky across turns), then the
    ContextVar is reset to the caller's instance.
    """
    run_state = current_agent_mode.get()
    parent_state.mode = run_state.mode
    current_agent_mode.reset(token)


def get_effective_policy() -> "PermissionPolicy | None":
    """The policy actually in force.

    Plan mode's read-only preset overrides any explicit policy; otherwise the
    explicit policy applies (``None`` → nothing constrained).
    """
    if current_agent_mode.get().mode == AgentMode.PLAN:
        return PLAN_MODE_POLICY
    return current_permission_policy.get()
