from abc import ABC, abstractmethod
from typing import List

from pydantic_ai import ModelMessage


class AnyHistoryManager(ABC):
    @abstractmethod
    def load(self, conversation_name: str) -> List[ModelMessage]:
        pass

    @abstractmethod
    def save(self, conversation_name: str):
        pass

    @abstractmethod
    def update(self, conversation_name: str, messages: List[ModelMessage]):
        pass
