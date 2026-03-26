from __future__ import annotations

from zrb.llm.approval.approval_channel import ApprovalContext, ApprovalResult


class NullApprovalChannel:
    """Approval channel that auto-approves everything.

    Useful for YOLO mode or when running in non-interactive environments
    where approval should be automatic.
    """

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
        pass
