from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)

if TYPE_CHECKING:
    from zrb.llm.chat.sse_ui import ChatSSEUI

logger = logging.getLogger(__name__)


class ChatApprovalChannel(ApprovalChannel):
    """Approval channel for web chat interface.

    This channel:
    - Registers approval requests with the session manager
    - Notifies SSE UI to broadcast approval prompts
    - Waits for resolution via API calls
    """

    def __init__(self):
        self._session_uis: dict[str, "ChatSSEUI"] = {}

    def register_ui(self, session_id: str, ui: "ChatSSEUI"):
        """Register a ChatSSEUI for a session."""
        self._session_uis[session_id] = ui

    def unregister_ui(self, session_id: str):
        """Unregister a ChatSSEUI for a session."""
        self._session_uis.pop(session_id, None)

    def get_ui(self, session_id: str) -> "ChatSSEUI | None":
        """Get the ChatSSEUI for a session."""
        return self._session_uis.get(session_id)

    async def request_approval(
        self,
        context: ApprovalContext,
    ) -> ApprovalResult:
        """Request approval for a tool call.

        Registers the pending approval with session manager and
        notifies the SSE UI to broadcast the approval request.
        Then waits for the user to respond via API.
        """
        from zrb.llm.chat.session_manager import chat_session_manager

        session_id = context.session_id
        if not session_id:
            logger.error("ChatApprovalChannel: No session_id in context")
            return ApprovalResult(approved=False, message="No session")

        try:
            future = await chat_session_manager.add_pending_approval(
                session_id, context
            )

            ui = self.get_ui(session_id)
            if ui:
                pending = {
                    "tool_call_id": context.tool_call_id,
                    "tool_name": context.tool_name,
                    "tool_args": context.tool_args,
                }
                await ui.on_approval_request(pending)

            result = await future

            if ui:
                await ui.on_approval_resolved(
                    context.tool_call_id,
                    "approved" if result.approved else "denied"
                )

            return result

        except asyncio.CancelledError:
            logger.warning(f"Approval cancelled for {context.tool_call_id}")
            return ApprovalResult(approved=False, message="Cancelled")
        except Exception as e:
            logger.error(f"Approval error: {e}")
            return ApprovalResult(approved=False, message=str(e))

    async def notify(
        self,
        message: str,
        context: ApprovalContext | None = None,
    ) -> None:
        """Send a notification to the SSE UI."""
        if context and context.session_id:
            ui = self.get_ui(context.session_id)
            if ui:
                await ui._broadcast("notification", message)


class ChatApprovalManager:
    """Manages approval actions from the web API.

    This class is used by the API routes to handle:
    - approve: Approve a tool call
    - deny: Deny a tool call
    - edit: Start edit mode for a tool call
    - edit_submit: Submit edited tool args
    """

    _instance: "ChatApprovalManager | None" = None

    def __init__(self):
        pass

    @classmethod
    def get_instance(cls) -> "ChatApprovalManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def approve(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> dict[str, Any]:
        """Approve a pending tool call."""
        from zrb.llm.approval.approval_channel import ApprovalResult
        from zrb.llm.chat.session_manager import chat_session_manager

        result = await chat_session_manager.resolve_approval(
            session_id,
            tool_call_id,
            ApprovalResult(approved=True, message="Approved via web"),
        )

        return {"success": result, "action": "approved"}

    async def deny(
        self,
        session_id: str,
        tool_call_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Deny a pending tool call."""
        from zrb.llm.approval.approval_channel import ApprovalResult
        from zrb.llm.chat.session_manager import chat_session_manager

        result = await chat_session_manager.resolve_approval(
            session_id,
            tool_call_id,
            ApprovalResult(approved=False, message=reason or "Denied via web"),
        )

        return {"success": result, "action": "denied"}

    async def start_edit(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> dict[str, Any]:
        """Start edit mode for a tool call."""
        from zrb.llm.chat.session_manager import chat_session_manager

        pending = await chat_session_manager.get_pending_approval(
            session_id, tool_call_id
        )
        if not pending:
            return {"success": False, "error": "Pending approval not found"}

        await chat_session_manager.set_waiting_for_edit(session_id, tool_call_id)

        return {
            "success": True,
            "action": "edit_started",
            "tool_name": pending.tool_name,
            "tool_args": pending.tool_args,
        }

    async def submit_edit(
        self,
        session_id: str,
        tool_call_id: str,
        new_args: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit edited tool arguments."""
        from zrb.llm.approval.approval_channel import ApprovalResult
        from zrb.llm.chat.session_manager import chat_session_manager

        result = await chat_session_manager.resolve_approval(
            session_id,
            tool_call_id,
            ApprovalResult(approved=True, override_args=new_args),
        )

        await chat_session_manager.set_waiting_for_edit(session_id, None)

        return {"success": result, "action": "edit_submitted"}


chat_approval_manager = ChatApprovalManager.get_instance()
