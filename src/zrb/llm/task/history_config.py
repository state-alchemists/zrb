"""The history knobs `LLMTask` and `LLMChatTask` both expose, grouped so they
cross the wrap boundary in `chat/execution.py` together.

That boundary builds the inner `LLMTask` with `dataclasses.replace()`, so a new
field passed through unchanged needs no edit there.
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
