from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.approval.any_approval_channel import (
    AnyApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)
from zrb.llm.tool_call.edit_util import edit_content_via_editor
from zrb.llm.tool_call.handler import ToolCallHandler

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI


class TerminalApprovalChannel(AnyApprovalChannel):
    """Default approval channel: asks through the UI's ``ask_user``."""

    def __init__(self, ui: "AnyUI"):
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

        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ToolCallPart

        call = ToolCallPart(
            tool_name=context.tool_name,
            args=context.tool_args,
            tool_call_id=context.tool_call_id,
        )

        # Use the UI's handler when it has one (it carries the formatters and
        # policies); `None` is the AnyUI contract's own "this UI has none".
        handler = self._ui.tool_call_handler or ToolCallHandler()

        message = await handler.format_approval_message(self._ui, call)
        CFG.LOGGER.debug(
            "TerminalApprovalChannel Got confirmation message, about to display to user"
        )
        # One leading "\n", not two — see the matching note in
        # `ToolCallHandler.handle`.
        self._ui.append_to_output(f"\n{message}", end="")

        CFG.LOGGER.debug("TerminalApprovalChannel Waiting for user input via CLI...")

        user_input = await self._ui.ask_user("", output_to_parent=f"\n{message}")
        user_response = user_input.strip()

        CFG.LOGGER.debug(
            f"TerminalApprovalChannel Got user response: '{user_response}'"
        )

        r = user_response.lower()
        if r in ("y", "yes", "ok", "accept", "✅", ""):
            return ApprovalResult(approved=True)
        if r in ("n", "no", "deny", "cancel", "🛑"):
            return ApprovalResult(approved=False, message="User denied")

        if r in ("e", "edit"):
            # The UI's response handlers (e.g. the diff-aware file-edit one)
            # go first; the raw-args editor is the fallback.
            result = await self._handle_via_response_handler(
                handler, call, user_response
            )
            if result is not None:
                return result
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
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ToolApproved, ToolDenied

        response_handlers = handler.get_response_handlers()

        async def next_handler(
            ui: Any,
            c: Any,
            r: str,
            index: int,
        ) -> Any:
            if index >= len(response_handlers):
                return ToolDenied("Edit not handled")
            resp_handler = response_handlers[index]
            return await resp_handler(
                ui, c, r, lambda u, cc, rr: next_handler(u, cc, rr, index + 1)
            )

        result = await next_handler(self._ui, call, response, 0)
        if isinstance(result, ToolApproved):
            return ApprovalResult(approved=True, override_args=result.override_args)
        return None

    async def _handle_edit(self, context: ApprovalContext) -> ApprovalResult:
        """Handle edit mode - open editor for new arguments."""
        current_args = context.tool_args or {}

        # Two-space indent matches the other mid-turn status lines printed
        # outside `StreamEventHandler` (see `web.py::_notify`).
        args_str = json.dumps(current_args, indent=2, default=str)
        self._ui.append_to_output(f"\n  📝 Current arguments:\n```\n{args_str}\n```\n")
        self._ui.append_to_output("  Opening editor...\n")

        new_args = await edit_content_via_editor(self._ui, current_args)

        if new_args is None:
            return ApprovalResult(
                approved=False, message="Failed to parse edited content"
            )

        if new_args == current_args:
            self._ui.append_to_output("  ℹ️ No changes made, approving original.\n")
            return ApprovalResult(approved=True)

        self._ui.append_to_output("  ✅ Approved with edited arguments.\n")
        return ApprovalResult(approved=True, override_args=new_args)

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Display notification to terminal."""
        self._ui.append_to_output(f"  {message}")
