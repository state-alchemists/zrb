"""Multi-channel approval for tool calls.

Routes a tool-call approval request somewhere other than terminal stdin —
Telegram, a web UI, Slack — through one contract, `AnyApprovalChannel`
(`request_approval` + `notify`). `TerminalApprovalChannel` is the default,
`NullApprovalChannel` auto-approves (YOLO), and `MultiplexApprovalChannel`
combines several channels first-response-wins; zrb builds that one itself when
a task carries more than one channel.

`docs/llm/llm-custom-ui.md` (section "Approval Channels") owns the how-to —
the interface, `ApprovalContext` fields, and dual-mode CLI-plus-external
wiring — with `examples/chat-telegram/` and `examples/chat-sse/` as the
runnable versions.
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
