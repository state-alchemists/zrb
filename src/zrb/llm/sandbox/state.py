"""Ambient sandbox state — the in-force sandbox policy.

Mirrors ``zrb.llm.permission.state``: an explicit policy bound by the runner
wins; otherwise the policy is resolved from ``CFG`` per call (cheap, and tests
or downstream products that patch config defaults are always honored).
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

from zrb.llm.sandbox.policy import SandboxPolicy, resolve_sandbox_policy_from_config
from zrb.util.contextvar_scope import scoped

current_sandbox_policy: ContextVar[SandboxPolicy | None] = ContextVar(
    "current_sandbox_policy", default=None
)


def get_current_sandbox_policy() -> SandboxPolicy | None:
    return current_sandbox_policy.get()


@contextmanager
def sandbox_policy(policy: "SandboxPolicy | None") -> Generator[None]:
    """Scope `policy` as the in-force sandbox policy for the `with` block.

    Always resets on exit, including on exception. The safe replacement for
    the old unscoped `set_current_sandbox_policy` (see `permission_policy`
    in `zrb.llm.permission.state` for the identical rationale).
    """
    with scoped(current_sandbox_policy, policy):
        yield


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
