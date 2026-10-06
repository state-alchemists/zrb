from __future__ import annotations

from zrb.llm.approval.any_approval_channel import (
    AnyApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)


class NullApprovalChannel(AnyApprovalChannel):
    """Approval channel that auto-approves everything (YOLO / non-interactive)."""

    async def request_approval(
        self,
        context: ApprovalContext,
    ) -> ApprovalResult:
        """Auto-approve all requests."""
        return ApprovalResult(approved=True)

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Ignore notifications."""
