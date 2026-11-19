from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolApproved, ToolDenied


@dataclass
class ApprovalContext:
    """Metadata about the tool call being approved, for channels to display."""

    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str
    session_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalResult:
    """Result of an approval request; converts to pydantic-ai's approval types."""

    approved: bool
    message: str = ""
    override_args: dict[str, Any] | None = None

    def to_pydantic_result(self) -> ToolApproved | ToolDenied:
        """Convert to Pydantic AI result types."""
        if self.approved:
            # lazy: zrb internal (heavy via transitive)
            from zrb.llm.agent.types import ToolApproved

            return ToolApproved(override_args=self.override_args)
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ToolDenied

        return ToolDenied(self.message)


class AnyApprovalChannel(ABC):
    """The approval-channel contract every backend implements.

    Routes approve/deny requests for tool executions through some interface
    (terminal, Telegram, web, Slack, ...). Async because it may wait on a
    remote user.
    """

    @abstractmethod
    async def request_approval(
        self,
        context: ApprovalContext,
    ) -> ApprovalResult:
        """Request approval for the tool call described by *context*."""

    @abstractmethod
    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Send a notification without requiring approval.

        Useful for showing intermediate status (tool started, completed, etc.).
        """
