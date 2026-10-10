"""Ambient sandbox policy; mirrors ``zrb.llm.permission.state``."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from zrb.llm.sandbox.policy import SandboxPolicy, resolve_sandbox_policy_from_config
from zrb.util.contextvar_scope import scoped

current_sandbox_policy: ContextVar[SandboxPolicy | None] = ContextVar(
    "current_sandbox_policy", default=None
)


def get_current_sandbox_policy() -> SandboxPolicy | None:
    return current_sandbox_policy.get()


@contextmanager
def sandbox_policy(policy: "SandboxPolicy | None") -> Generator[None]:
    """Scope `policy` as the in-force sandbox policy for the `with` block."""
    with scoped(current_sandbox_policy, policy):
        yield


def get_effective_sandbox_policy() -> SandboxPolicy:
    """The explicitly bound policy, else one resolved from ``CFG`` per call."""
    explicit = current_sandbox_policy.get()
    if explicit is not None:
        return explicit
    return resolve_sandbox_policy_from_config()
