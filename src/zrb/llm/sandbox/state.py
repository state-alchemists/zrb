"""Ambient sandbox state — the in-force sandbox policy.

Mirrors ``zrb.llm.permission.state``: an explicit policy bound by the runner
wins; otherwise the policy is resolved from ``CFG`` per call (cheap, and tests
or downstream products that patch config defaults are always honored).
"""

from __future__ import annotations

from contextvars import ContextVar

from zrb.llm.sandbox.policy import SandboxPolicy, resolve_sandbox_policy_from_config

current_sandbox_policy: ContextVar[SandboxPolicy | None] = ContextVar(
    "current_sandbox_policy", default=None
)


def get_current_sandbox_policy() -> SandboxPolicy | None:
    return current_sandbox_policy.get()


def set_current_sandbox_policy(policy: SandboxPolicy | None) -> None:
    current_sandbox_policy.set(policy)


def get_effective_sandbox_policy() -> SandboxPolicy:
    """The sandbox policy actually in force.

    The explicit (runner-bound, sub-agent-inherited) policy wins; otherwise
    resolve from ``CFG.LLM_SANDBOX_*`` — which is ``enabled=False`` unless the
    deployment opted in.
    """
    explicit = current_sandbox_policy.get()
    if explicit is not None:
        return explicit
    return resolve_sandbox_policy_from_config()
