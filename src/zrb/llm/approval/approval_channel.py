from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolDenied


@dataclass
class ApprovalContext:
    """Context information for approval requests.

    Provides metadata about the tool call being approved, making it easier
    for approval channels to display rich information to users.
    """

    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str
    session_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalResult:
    """Result of an approval request.

    Wraps the Pydantic AI approval/denial types for a cleaner interface.
    """

    approved: bool
    message: str = ""
    override_args: dict[str, Any] | None = None

    def to_pydantic_result(self) -> ToolApproved | ToolDenied:
        """Convert to Pydantic AI result types."""
        if self.approved:
            from pydantic_ai import ToolApproved

            return ToolApproved(override_args=self.override_args)
        else:
            from pydantic_ai import ToolDenied

            return ToolDenied(self.message)


@runtime_checkable
class ApprovalChannel(Protocol):
    """Protocol for approval channels.

    An approval channel handles requests to approve/deny tool executions.
    Implementations can route approvals through different interfaces:
    - Terminal (stdin/stdout)
    - Telegram bot
    - Web interface
    - Slack
    - WhatsApp
    - etc.

    The channel must be async since it may need to wait for user input
    from remote sources (e.g., waiting for Telegram message).
    """

    async def request_approval(
        self,
        context: ApprovalContext,
    ) -> ApprovalResult:
        """Request approval for a tool call.

        Args:
            context: Context containing tool call details and metadata.

        Returns:
            ApprovalResult indicating approval or denial with optional message.
        """
        ...

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Send a notification without requiring approval.

        Useful for showing intermediate status (tool started, completed, etc.).

        Args:
            message: The notification message.
            context: Optional context for metadata.
        """
        ...


# Context variable for propagating approval channel to nested agents
current_approval_channel: ContextVar[ApprovalChannel | None] = ContextVar(
    "current_approval_channel", default=None
)
