from __future__ import annotations

from contextvars import ContextVar

from zrb.llm.approval.any_approval_channel import (
    AnyApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)

__all__ = [
    "AnyApprovalChannel",
    "ApprovalContext",
    "ApprovalResult",
    "current_approval_channel",
]

# Context variable for propagating approval channel to nested agents
current_approval_channel: ContextVar[AnyApprovalChannel | None] = ContextVar(
    "current_approval_channel", default=None
)
