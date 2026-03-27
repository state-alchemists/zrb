from __future__ import annotations

import json

from zrb.config.config import CFG
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

        handler = ToolCallHandler()
        message = await handler._get_confirm_user_message(self._ui, call)
        CFG.LOGGER.debug(
            "TerminalApprovalChannel Got confirmation message, about to display to user"
        )
        self._ui.append_to_output(f"\n\n{message}", end="")
        self._ui.append_to_output(
            "\n\n  [y] Yes  [n] No  [e] Edit args  [default: Yes]: ",
            end="",
        )

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

        # Handle edit mode
        if r in ("e", "edit"):
            return await self._handle_edit(context)

        return ApprovalResult(
            approved=False, message=f"User denied with: {user_response}"
        )

    async def _handle_edit(self, context: ApprovalContext) -> ApprovalResult:
        """Handle edit mode - ask for new arguments."""
        import yaml

        # Show current args
        current_args = context.tool_args or {}
        args_str = json.dumps(current_args, indent=2, default=str)
        self._ui.append_to_output(f"\n📝 Current arguments:\n```\n{args_str}\n```\n")
        self._ui.append_to_output(
            "Enter new arguments (JSON or YAML, or 'cancel' to abort):\n"
        )

        # Get new args
        user_input = await self._ui.ask_user("")
        user_input = user_input.strip()

        if user_input.lower() in ("cancel", "c", "abort"):
            return ApprovalResult(approved=False, message="User cancelled edit")

        # Try to parse as JSON
        try:
            new_args = json.loads(user_input)
            self._ui.append_to_output(f"✅ Approved with edited args\n")
            return ApprovalResult(approved=True, override_args=new_args)
        except json.JSONDecodeError:
            pass

        # Try to parse as YAML
        try:
            new_args = yaml.safe_load(user_input)
            if isinstance(new_args, dict):
                self._ui.append_to_output(f"✅ Approved with edited args\n")
                return ApprovalResult(approved=True, override_args=new_args)
        except yaml.YAMLError:
            pass

        return ApprovalResult(
            approved=False, message="Invalid JSON/YAML format for edited args"
        )

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Display notification to terminal."""
        self._ui.append_to_output(message)
