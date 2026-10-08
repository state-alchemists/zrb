"""Capture run-scoped authority for delayed sub-agent continuations.

Continuations run after the originating ``ContextVar`` scope exits, so they
must receive the original permission, sandbox, yolo, hook and approval
settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.agent_state import (
    AnyToolConfirmation,
    get_current_approval_channel,
    get_current_hook_manager,
    get_current_tool_confirmation,
    get_current_yolo,
)
from zrb.llm.permission.policy import PermissionPolicy
from zrb.llm.permission.state import get_effective_policy
from zrb.llm.sandbox.policy import SandboxPolicy
from zrb.llm.sandbox.state import get_effective_sandbox_policy

if TYPE_CHECKING:
    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.hook.manager import HookManager


@dataclass(frozen=True)
class AuthoritySnapshot:
    """What a delegation was actually granted, captured once at creation."""

    permission_policy: PermissionPolicy | None
    yolo: bool
    sandbox_policy: SandboxPolicy
    # The parent run's hook manager, captured with the rest: a continuation
    # that starts after the parent's scope has exited must still fire on the
    # same manager rather than fall back to the process-wide singleton.
    hook_manager: "HookManager | None"
    # The parent's approval handler (its tool policies, argument formatters
    # and response handlers) and approval channel: without them a
    # continuation's tool calls skip the policies its first turn ran under.
    tool_confirmation: AnyToolConfirmation = None
    approval_channel: "AnyApprovalChannel | None" = None


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
        hook_manager=get_current_hook_manager(),
        tool_confirmation=get_current_tool_confirmation(),
        approval_channel=get_current_approval_channel(),
    )
