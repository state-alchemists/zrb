"""Ambient sandbox policy; mirrors ``zrb.llm.permission.state``."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace

from zrb.llm.sandbox.policy import SandboxPolicy, resolve_sandbox_policy_from_config
from zrb.llm.contracts.shared.agent_state import get_current_ui
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
    """The bound policy, else the session's switch, else one built from ``CFG``.

    Resolved per call, so a `/sandbox` typed mid-answer reaches the next tool
    call. The session's switch is read from its own UI rather than written into
    ``CFG``: that config is the deployment's, and a choice made in one
    conversation must not decide what a second conversation is contained by.
    """
    explicit = current_sandbox_policy.get()
    if explicit is not None:
        return explicit
    policy = resolve_sandbox_policy_from_config()
    override = sandbox_override_of(get_current_ui())
    if override is None:
        return policy
    return replace(policy, enabled=override)


def sandbox_override_of(ui: object) -> bool | None:
    """A UI's `/sandbox` choice, or None when it never made one.

    `getattr` plus the ``isinstance`` filter rather than a plain attribute
    read: a headless UI need not carry the tools role, and a stand-in's
    auto-created attribute is a mock, not a decision.
    """
    value = getattr(getattr(ui, "tools", None), "sandbox_override", None)
    return value if isinstance(value, bool) else None


def sandbox_run_policy_of(ui: object) -> bool | None:
    """The containment the run in `ui`'s session asked for, else None.

    The runner publishes it, because the gate reads a run's policy through
    `deps` while everything that *draws* the session — the status bar, a badge
    — runs in another task, where the run's context variables are invisible.
    Without this, `LLMTask(sandbox=True)` over a deployment that has it off
    contains every tool call and announces none of them.
    """
    value = getattr(getattr(ui, "tools", None), "sandbox_run_policy", None)
    return value if isinstance(value, bool) else None


def is_sandbox_enabled_for(ui: object) -> bool:
    """Whether the session behind `ui` is contained right now.

    The run's own policy first, then the session's switch, then the
    deployment's config — the order the gate resolves in, so the answer a
    status bar prints is the answer a tool call gets. Asking this of a *named*
    UI rather than the ambient one is what lets a switch and a status bar agree
    about their own session while no run is bound.
    """
    run_policy = sandbox_run_policy_of(ui)
    if run_policy is not None:
        return run_policy
    override = sandbox_override_of(ui)
    if override is not None:
        return override
    return get_effective_sandbox_policy().enabled
