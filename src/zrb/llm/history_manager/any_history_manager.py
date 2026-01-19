from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage


class AnyHistoryManager(ABC):
    @abstractmethod
    def load(self, conversation_name: str) -> "list[ModelMessage]":
        pass

    @abstractmethod
    def save(self, conversation_name: str):
        pass

    @abstractmethod
    def update(self, conversation_name: str, messages: "list[ModelMessage]"):
        pass

    @abstractmethod
    def search(self, keyword: str) -> list[str]:
        pass
