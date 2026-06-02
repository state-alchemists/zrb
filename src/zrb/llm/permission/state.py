"""Ambient permission state — the in-force policy and agent mode.

``current_agent_mode`` is a ``ContextVar`` whose value is a **mutable**
``AgentModeState`` instance.  pydantic-ai spawns a fresh task per tool call
(``_agent_graph.py:1873``), which snapshots the current ``ContextVar`` values.
With an immutable ``AgentMode`` enum the change made by ``ExitPlanMode`` is
lost — the next tool's task sees the snapshot.  By mutating an attribute on
a shared instance, every task sees the update.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum

from zrb.llm.permission.policy import PLAN_MODE_POLICY, PermissionPolicy


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


def set_current_permission_policy(policy: "PermissionPolicy | None") -> None:
    current_permission_policy.set(policy)


def get_current_agent_mode() -> AgentMode:
    return current_agent_mode.get().mode


def set_current_agent_mode(mode: AgentMode) -> None:
    """Set agent mode on the shared mutable state so every task sees it."""
    current_agent_mode.get().mode = mode


def get_effective_policy() -> "PermissionPolicy | None":
    """The policy actually in force.

    Plan mode's read-only preset overrides any explicit policy; otherwise the
    explicit policy applies (``None`` → legacy behavior, nothing constrained).
    """
    if current_agent_mode.get().mode == AgentMode.PLAN:
        return PLAN_MODE_POLICY
    return current_permission_policy.get()
