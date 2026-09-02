"""Multi-channel approval system for Zrb.

This module provides a flexible approval channel system that allows tool call
approvals to be routed through different channels (Terminal, Telegram, Web, etc.)
instead of only terminal input.

APPROVAL CHANNEL HIERARCHY
═════════════════════════════════════════════════════════════════════════════

    ┌────────────────────────────────────────────────────────────────────────┐
    │ AnyApprovalChannel (ABC)                                               │
    │   - request_approval(context): Wait for user approval                  │
    │   - notify(message, context): Send informational message               │
    │   - Implement for custom backends                                      │
    ├────────────────────────────────────────────────────────────────────────┤
    │ Built-in Implementations:                                              │
    ├────────────────────────────────────────────────────────────────────────┤
    │ TerminalApprovalChannel                                                │
    │   - Uses AnyUI for terminal interaction                                │
    │   - Default when no custom channel is set                              │
    │                                                                        │
    │ NullApprovalChannel                                                    │
    │   - Auto-approves all tool calls (YOLO mode)                           │
    │   - Use: llm_chat.approval_channels = [NullApprovalChannel()]          │
    │                                                                        │
    │ MultiplexApprovalChannel                                               │
    │   - Combines multiple approval channels                                │
    │   - First response wins (any channel can approve)                      │
    │   - Auto-created when multiple channels are added                      │
    └────────────────────────────────────────────────────────────────────────┘

SIMPLE APPROVAL CHANNEL
═════════════════════════════════════════════════════════════════════════════

Basic implementation (just approve/deny):

    from zrb.llm.approval import AnyApprovalChannel, ApprovalContext, ApprovalResult

    class MyApprovalChannel(AnyApprovalChannel):
        async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
            # Send approval request (e.g., via Telegram button, webhook)
            ...
            return ApprovalResult(approved=True)  # or False

        async def notify(self, message: str, context: ApprovalContext = None):
            # Send notification
            ...

    # Register
    from zrb.builtin.llm.chat import llm_chat
    llm_chat.approval_channels = [MyApprovalChannel(...)]

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

from zrb.llm.approval.any_approval_channel import (
    AnyApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.approval.multiplex_approval_channel import (
    MultiplexApprovalChannel,
    resolve_approval_channel,
)
from zrb.llm.approval.null_approval_channel import NullApprovalChannel
from zrb.llm.approval.terminal_approval_channel import TerminalApprovalChannel

__all__ = [
    "AnyApprovalChannel",
    "ApprovalContext",
    "ApprovalResult",
    "current_approval_channel",
    "MultiplexApprovalChannel",
    "NullApprovalChannel",
    "TerminalApprovalChannel",
    "resolve_approval_channel",
]
