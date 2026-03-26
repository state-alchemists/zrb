from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ApprovalContext:
    tool_name: str
    tool_args: Any  # Preserve raw structure (dict, str, provider-wrapped, etc.)
    tool_call_id: str
    session_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalResult:
    approved: bool
    message: str = ""
    edited_args: Any | None = None  # Preserve raw structure

    def to_pydantic_result(self):
        from pydantic_ai import ToolApproved, ToolDenied

        if self.approved:
            return ToolApproved(override_args=self.edited_args)
        msg = self.message or "Execution denied by user."
        return ToolDenied(msg)


class ApprovalChannel(Protocol):
    async def request_approval(self, context: ApprovalContext) -> ApprovalResult: ...
    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None: ...


current_approval_channel: ContextVar[ApprovalChannel | None] = ContextVar(
    "current_approval_channel", default=None
)
