"""The history-related knobs `LLMTask` and `LLMChatTask` both expose,
grouped so they travel together across the wrap boundary in
`chat/execution.py::_create_llm_task_core`.

That boundary builds the inner `LLMTask` from `LLMChatTask`'s own settings,
overriding each field that needs a chat-specific value (today, all three do —
the inner task's conversation identity is always the active chat session, not
whatever `LLMChatTask` happened to be configured with). Grouping them means a
future field only *read straight through unchanged* costs an edit here plus
wherever it's consumed (`task/history.py`) — `dataclasses.replace()` forwards
it through the wrap boundary automatically, rather than requiring a fourth
edit there just to notice the new field exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.attr.type import StrAttr
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


@dataclass(frozen=True)
class HistoryConfig:
    history_manager: "AnyHistoryManager | None" = None
    conversation_name: "StrAttr | None" = None
    render_conversation_name: bool = True
