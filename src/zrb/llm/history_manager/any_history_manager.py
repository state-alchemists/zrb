from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage


class AnyHistoryManager(ABC):
    @property
    def storage_dir(self) -> str | None:
        """The directory this manager stores conversations in, or ``None``.

        A store that keeps conversations somewhere else (a database, a remote
        service) has no directory; callers that need a file beside the history
        — the verbatim archive — then fall back to the configured history dir.
        """
        return None

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
    def search(
        self,
        keyword: str,
        include_delegated: bool = True,
        include_empty: bool = True,
    ) -> list[str]:
        """Conversation names matching `keyword`; `include_delegated=False`
        omits sub-agent transcripts (those stored under `subagent/`), and
        `include_empty=False` omits conversations with no messages."""
        pass
