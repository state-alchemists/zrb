from __future__ import annotations

from zrb.llm.approval.channel import ApprovalChannel, ApprovalContext, ApprovalResult


class NullApprovalChannel:
    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        return ApprovalResult(approved=True)

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        return None
