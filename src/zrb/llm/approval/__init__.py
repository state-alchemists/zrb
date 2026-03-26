"""Multi-channel approval system for Zrb.

This module provides a flexible approval channel system that allows tool call
approvals to be routed through different channels (Terminal, Telegram, Web, etc.)
instead of only terminal input.

Extension Hierarchy:
    ┌─────────────────────────────────────────────────────────────────┐
    │ Level 0: ApprovalChannel (Protocol, 2 methods)                  │
    │         - request_approval(), notify()                          │
    │         - Implement for custom backends                        │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 1: TerminalApprovalChannel (built-in)                     │
    │         - Uses UIProtocol for terminal interaction              │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 2: NullApprovalChannel (auto-approve)                     │
    │         - Approves everything without interaction              │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

    # Implement for custom backend (Telegram, Discord, etc.)
    class MyApprovalChannel:
        async def request_approval(self, context: ApprovalContext):
            # Send approval request with buttons
            ...
            return ApprovalResult(approved=True)

        async def notify(self, message: str, context: ApprovalContext = None):
            # Send notification
            ...

    # Set on llm_chat task
    from zrb.builtin.llm.chat import llm_chat
    llm_chat.set_approval_channel(MyApprovalChannel(...))

    # See examples/chat-telegram/ for a complete example.
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
