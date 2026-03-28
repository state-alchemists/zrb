"""Multi-channel approval system for Zrb.

This module provides a flexible approval channel system that allows tool call
approvals to be routed through different channels (Terminal, Telegram, Web, etc.)
instead of only terminal input.

APPROVAL CHANNEL HIERARCHY
═════════════════════════════════════════════════════════════════════════════

    ┌────────────────────────────────────────────────────────────────────────┐
    │ ApprovalChannel (Protocol)                                             │
    │   - request_approval(context): Wait for user approval                  │
    │   - notify(message, context): Send informational message               │
    │   - Implement for custom backends                                      │
    ├────────────────────────────────────────────────────────────────────────┤
    │ Built-in Implementations:                                              │
    ├────────────────────────────────────────────────────────────────────────┤
    │ TerminalApprovalChannel                                                │
    │   - Uses UIProtocol for terminal interaction                           │
    │   - Default when no custom channel is set                              │
    │                                                                        │
    │ NullApprovalChannel                                                    │
    │   - Auto-approves all tool calls (YOLO mode)                           │
    │   - Use: llm_chat.set_approval_channel(NullApprovalChannel())          │
    │                                                                        │
    │ MultiplexApprovalChannel                                               │
    │   - Combines multiple approval channels                                │
    │   - First response wins (any channel can approve)                      │
    │   - Auto-created when multiple channels are added                      │
    └────────────────────────────────────────────────────────────────────────┘

SIMPLE APPROVAL CHANNEL
═════════════════════════════════════════════════════════════════════════════

Basic implementation (just approve/deny):

    from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

    class MyApprovalChannel(ApprovalChannel):
        async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
            # Send approval request (e.g., via Telegram button, webhook)
            ...
            return ApprovalResult(approved=True)  # or False

        async def notify(self, message: str, context: ApprovalContext = None):
            # Send notification
            ...

    # Register
    from zrb.builtin.llm.chat import llm_chat
    llm_chat.set_approval_channel(MyApprovalChannel(...))

DUAL-MODE APPROVAL (CLI + External Channel)
═════════════════════════════════════════════════════════════════════════════

For dual-mode (CLI + Telegram/SSE), add multiple approval channels:

    from zrb.llm.approval import (
        MultiplexApprovalChannel,
        TerminalApprovalChannel,
    )
    from zrb.builtin.llm.chat import llm_chat

    # Add Telegram approval channel
    llm_chat.append_approval_channel(TelegramApprovalChannel(bot, chat_id))

    # Terminal approval is handled automatically
    # Framework creates MultiplexApprovalChannel automatically

    # See examples/chat-telegram/ for complete implementation
"""

from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
    current_approval_channel,
)
from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel
from zrb.llm.approval.null_approval_channel import NullApprovalChannel
from zrb.llm.approval.terminal_approval_channel import TerminalApprovalChannel

__all__ = [
    "ApprovalChannel",
    "ApprovalContext",
    "ApprovalResult",
    "current_approval_channel",
    "MultiplexApprovalChannel",
    "NullApprovalChannel",
    "TerminalApprovalChannel",
]
