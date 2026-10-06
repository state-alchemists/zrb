"""History knobs shared by `LLMTask` and `LLMChatTask`, passed as one unit to the
inner task in `chat/execution.py` via `dataclasses.replace()`.
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
