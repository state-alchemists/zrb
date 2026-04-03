from typing import TYPE_CHECKING

from zrb.llm.history_manager.any_history_manager import AnyHistoryManager

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage


class NoSaveHistoryManager(AnyHistoryManager):
    """
    An ephemeral history manager that loads from a pre-populated history
    but never persists changes to disk.

    Used by the /btw side-question feature to provide conversation context
    without polluting the permanent session history.
    """

    def __init__(self, initial_history: "list[ModelMessage]"):
        self._history: list = list(initial_history)

    def load(self, conversation_name: str) -> "list[ModelMessage]":
        return list(self._history)

    def save(self, conversation_name: str) -> None:
        pass  # Intentionally a no-op

    def update(self, conversation_name: str, messages: "list[ModelMessage]") -> None:
        pass  # Intentionally a no-op

    def search(self, keyword: str) -> list[str]:
        return []
