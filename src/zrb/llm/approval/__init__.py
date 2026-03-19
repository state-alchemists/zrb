"""Multi-channel approval system for Zrb.

This module provides a flexible approval channel system that allows tool call
approvals to be routed through different channels (Terminal, Telegram, Web, etc.)
instead of only terminal input.
"""

from zrb.llm.approval.channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
    NullApprovalChannel,
    TerminalApprovalChannel,
    current_approval_channel,
)
from zrb.llm.approval.factory import load_approval_channel

__all__ = [
    "ApprovalChannel",
    "ApprovalContext",
    "ApprovalResult",
    "current_approval_channel",
    "NullApprovalChannel",
    "TerminalApprovalChannel",
    "load_approval_channel",
]