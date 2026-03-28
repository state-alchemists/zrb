from __future__ import annotations

import json

from zrb.config.config import CFG
from zrb.llm.approval.approval_channel import ApprovalContext, ApprovalResult
from zrb.llm.tool_call.edit_util import edit_content_via_editor
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
        import sys

        CFG.LOGGER.debug(
            f"TerminalApprovalChannel START request_approval for {context.tool_name}"
        )
        CFG.LOGGER.debug(
            f"TerminalApprovalChannel context.tool_args: {context.tool_args}"
        )

        # Format the approval message
        from pydantic_ai import ToolCallPart

        from zrb.llm.tool_call.handler import ToolCallHandler

        # Create a mock ToolCallPart for formatting
        call = ToolCallPart(
            tool_name=context.tool_name,
            args=context.tool_args,
            tool_call_id=context.tool_call_id,
        )

        # Use the UI's handler if available (has formatters), otherwise create new one
        handler = None
        if (
            hasattr(self._ui, "_tool_call_handler")
            and self._ui._tool_call_handler is not None
        ):
            handler = self._ui._tool_call_handler
        else:
            handler = ToolCallHandler()

        # Use public method for approval message with custom instruction
        message = await handler.format_approval_message(self._ui, call)
        CFG.LOGGER.debug(
            "TerminalApprovalChannel Got confirmation message, about to display to user"
        )
        self._ui.append_to_output(f"\n\n{message}", end="")

        CFG.LOGGER.debug("TerminalApprovalChannel Waiting for user input via CLI...")

        # Wait for user input
        user_input = await self._ui.ask_user("")
        user_response = user_input.strip()

        CFG.LOGGER.debug(
            f"TerminalApprovalChannel Got user response: '{user_response}'"
        )

        # Parse response
        r = user_response.lower().strip()
        if r in ("y", "yes", "ok", "accept", "✅", ""):
            return ApprovalResult(approved=True)
        if r in ("n", "no", "deny", "cancel", "🛑"):
            return ApprovalResult(approved=False, message="User denied")

        # Handle edit mode - use response handler chain if available
        if r in ("e", "edit"):
            # Use the UI's response handlers (e.g., replace_in_file_response_handler)
            # which shows diff and handles editing properly
            result = await self._handle_via_response_handler(
                handler, call, user_response
            )
            if result is not None:
                return result
            # Fall back to simple edit if no response handler handled it
            return await self._handle_edit(context)

        return ApprovalResult(
            approved=False, message=f"User denied with: {user_response}"
        )

    async def _handle_via_response_handler(
        self,
        handler: Any,
        call: Any,
        response: str,
    ) -> ApprovalResult | None:
        """Handle edit via response handler chain (like ToolCallHandler does)."""
        from pydantic_ai import ToolApproved, ToolDenied

        # Use public getter for response handlers
        response_handlers = handler.get_response_handlers()

        async def next_handler(
            ui: Any,
            c: Any,
            r: str,
            index: int,
        ) -> Any:
            if index >= len(response_handlers):
                # Default behavior - deny
                return ToolDenied("Edit not handled")
            resp_handler = response_handlers[index]
            return await resp_handler(
                ui, c, r, lambda u, cc, rr: next_handler(u, cc, rr, index + 1)
            )

        result = await next_handler(self._ui, call, response, 0)
        if isinstance(result, ToolApproved):
            return ApprovalResult(approved=True, override_args=result.override_args)
        elif isinstance(result, ToolDenied):
            # Response handler denied or didn't handle it
            return None
        return None

    async def _handle_edit(self, context: ApprovalContext) -> ApprovalResult:
        """Handle edit mode - open editor for new arguments."""
        current_args = context.tool_args or {}

        # Show current args
        args_str = json.dumps(current_args, indent=2, default=str)
        self._ui.append_to_output(f"\n📝 Current arguments:\n```\n{args_str}\n```\n")
        self._ui.append_to_output("Opening editor...\n")

        # Open editor via shared utility
        new_args = await edit_content_via_editor(self._ui, current_args)

        if new_args is None:
            return ApprovalResult(
                approved=False, message="Failed to parse edited content"
            )

        if new_args == current_args:
            self._ui.append_to_output("ℹ️ No changes made, approving original.\n")
            return ApprovalResult(approved=True)

        self._ui.append_to_output("✅ Approved with edited arguments.\n")
        return ApprovalResult(approved=True, override_args=new_args)

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Display notification to terminal."""
        self._ui.append_to_output(message)
