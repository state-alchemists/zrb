"""Capture ambient authority (permission policy, yolo, sandbox) for later reuse.

`run_agent`'s inheritance model ("a sub-agent must not exceed its parent",
ADR-0069) relies on `asyncio.create_task`/`ensure_future` copying the current
`ContextVar` context — correct whenever the detached task is spawned *while
the originating scope is still bound*. A continuation spawned later, after
that scope has already exited (`live_session.py`'s `_continue_live_session`,
which runs long after the original delegation's `run_agent()` call already
returned and reset its `ExitStack`-bound ContextVars), sees whatever is
ambient at that later, unrelated point instead — which can be broader than
what was originally granted.

Capture an `AuthoritySnapshot` once, while the originating scope is still
bound, and pass its fields explicitly to the later `run_agent()` call instead
of relying on ambient inheritance at that point.
"""

from __future__ import annotations

from dataclasses import dataclass

from zrb.llm.agent_state import get_current_yolo
from zrb.llm.permission.policy import PermissionPolicy
from zrb.llm.permission.state import get_effective_policy
from zrb.llm.sandbox.policy import SandboxPolicy
from zrb.llm.sandbox.state import get_effective_sandbox_policy


@dataclass(frozen=True)
class AuthoritySnapshot:
    """What a delegation was actually granted, captured once at creation."""

    permission_policy: PermissionPolicy | None
    yolo: bool
    sandbox_policy: SandboxPolicy


def capture_current_authority(yolo_override: bool | None = None) -> AuthoritySnapshot:
    """Capture the authority in effect right now.

    `yolo_override` is the explicit per-call override a caller may pass to
    `run_agent` (e.g. `run_agent_task`'s `yolo` argument) — `None` means
    "inherit", matching `run_agent`'s own resolution of that argument.
    """
    return AuthoritySnapshot(
        permission_policy=get_effective_policy(),
        yolo=yolo_override if yolo_override is not None else get_current_yolo(),
        sandbox_policy=get_effective_sandbox_policy(),
    )
