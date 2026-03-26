from __future__ import annotations

from zrb.llm.approval.approval_channel import ApprovalContext, ApprovalResult
from zrb.llm.tool_call.ui_protocol import UIProtocol


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
        print(
            f"[DEBUG TerminalApprovalChannel] START request_approval for {context.tool_name}"
        )
        print(f"[DEBUG TerminalApprovalChannel] context.tool_args: {context.tool_args}")

        # Format the approval message
        from pydantic_ai import ToolCallPart

        from zrb.llm.tool_call.handler import ToolCallHandler

        # Create a mock ToolCallPart for formatting
        call = ToolCallPart(
            tool_name=context.tool_name,
            args=context.tool_args,
            tool_call_id=context.tool_call_id,
        )

        handler = ToolCallHandler()
        message = await handler._get_confirm_user_message(self._ui, call)
        print(
            f"[DEBUG TerminalApprovalChannel] Got confirmation message, about to display to user"
        )
        self._ui.append_to_output(f"\n\n{message}", end="")

        print(f"[DEBUG TerminalApprovalChannel] Waiting for user input via CLI...")

        # Wait for user input
        user_input = await self._ui.ask_user("")
        user_response = user_input.strip()

        print(f"[DEBUG TerminalApprovalChannel] Got user response: '{user_response}'")

        # Parse response
        r = user_response.lower().strip()
        if r in ("y", "yes", "ok", "accept", "✅", ""):
            return ApprovalResult(approved=True)
        if r in ("n", "no", "deny", "cancel", "🛑"):
            return ApprovalResult(approved=False, message="User denied")

        return ApprovalResult(
            approved=False, message=f"User denied with: {user_response}"
        )

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Display notification to terminal."""
        self._ui.append_to_output(message)
