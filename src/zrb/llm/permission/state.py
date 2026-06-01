"""Ambient permission state — the in-force policy and agent mode.

Both are ``ContextVar``s so sub-agents inherit them live, exactly like
``current_yolo`` in the runner. Defaults reproduce today's behavior: no policy
(``None``) and ``AgentMode.DEFAULT``.
"""

from __future__ import annotations

from contextvars import ContextVar
from enum import Enum

from zrb.llm.permission.policy import PLAN_MODE_POLICY, PermissionPolicy


class AgentMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"


current_permission_policy: ContextVar[PermissionPolicy | None] = ContextVar(
    "current_permission_policy", default=None
)
current_agent_mode: ContextVar[AgentMode] = ContextVar(
    "current_agent_mode", default=AgentMode.DEFAULT
)


def get_current_permission_policy() -> "PermissionPolicy | None":
    return current_permission_policy.get()


def set_current_permission_policy(policy: "PermissionPolicy | None") -> None:
    current_permission_policy.set(policy)


def get_current_agent_mode() -> AgentMode:
    return current_agent_mode.get()


def set_current_agent_mode(mode: AgentMode) -> None:
    current_agent_mode.set(mode)


def get_effective_policy() -> "PermissionPolicy | None":
    """The policy actually in force.

    Plan mode's read-only preset overrides any explicit policy; otherwise the
    explicit policy applies (``None`` → legacy behavior, nothing constrained).
    """
    if current_agent_mode.get() == AgentMode.PLAN:
        return PLAN_MODE_POLICY
    return current_permission_policy.get()
