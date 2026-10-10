from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage


class AnyHistoryManager(ABC):
    @abstractmethod
    def load(self, conversation_name: str) -> "list[ModelMessage]":
        pass

    @abstractmethod
    def save(self, conversation_name: str, write_backup: bool = True):
        pass

    @abstractmethod
    def update(self, conversation_name: str, messages: "list[ModelMessage]"):
        pass

    @abstractmethod
    def search(self, keyword: str, include_delegated: bool = True) -> list[str]:
        """Conversation names matching `keyword`; `include_delegated=False`
        omits sub-agent transcripts (those stored under `subagent/`)."""
        pass
