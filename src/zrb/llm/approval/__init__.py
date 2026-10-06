"""Multi-channel approval for tool calls.

See `docs/llm/llm-custom-ui.md` ("Approval Channels") and
`examples/chat-telegram/`, `examples/chat-sse/`.
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
