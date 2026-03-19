"""Approval Channel Protocol and implementations.

Provides a flexible approval system that can route tool call approvals
through different channels (Terminal, Telegram, Web, etc.).
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied


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

    def to_pydantic_result(self) -> ToolApproved | ToolDenied:
        """Convert to Pydantic AI result types."""
        if self.approved:
            from pydantic_ai import ToolApproved

            return ToolApproved()
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


class TerminalApprovalChannel:
    """Default approval channel using terminal input.

    This wraps the existing UIProtocol.ask_user() pattern for backward
    compatibility while conforming to the ApprovalChannel protocol.
    """

    def __init__(self, ui: "UIProtocol"):
        """Initialize with a UIProtocol instance.

        Args:
            ui: The UI to use for terminal interaction.
        """
        self._ui = ui

    async def request_approval(
        self,
        context: ApprovalContext,
    ) -> ApprovalResult:
        """Request approval via terminal."""
        # Format the approval message
        from zrb.llm.tool_call.handler import ToolCallHandler
        from pydantic_ai import ToolCallPart

        # Create a mock ToolCallPart for formatting
        call = ToolCallPart(
            tool_name=context.tool_name,
            args=context.tool_args,
            tool_call_id=context.tool_call_id,
        )

        handler = ToolCallHandler()
        message = await handler._get_confirm_user_message(self._ui, call)
        self._ui.append_to_output(f"\n\n{message}", end="")

        # Wait for user input
        user_input = await self._ui.ask_user("")
        user_response = user_input.strip()

        # Parse response
        r = user_response.lower().strip()
        if r in ("y", "yes", "ok", "accept", "✅", ""):
            return ApprovalResult(approved=True)
        if r in ("n", "no", "deny", "cancel", "🛑"):
            return ApprovalResult(approved=False, message="User denied")

        return ApprovalResult(approved=False, message=f"User denied with: {user_response}")

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Display notification to terminal."""
        self._ui.append_to_output(message)


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


if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import UIProtocol