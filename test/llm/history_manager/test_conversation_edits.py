"""Tests for `zrb.llm.history_manager.conversation_edits`."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.history_manager.conversation_edits import (
    copy_conversation,
    truncate_conversation,
)

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage


def _messages(count: int) -> list[ModelMessage]:
    return [MagicMock(name=f"m{index}") for index in range(count)]


class _MemoryHistoryManager(AnyHistoryManager):
    """A store that keeps conversations in a dict and counts its writes."""

    def __init__(self, conversations: dict[str, list[ModelMessage]] | None = None):
        self.conversations = dict(conversations or {})
        self.saved: list[str] = []

    def load(self, conversation_name: str) -> list[ModelMessage]:
        return list(self.conversations.get(conversation_name, []))

    def update(self, conversation_name: str, messages: list[ModelMessage]) -> None:
        self.conversations[conversation_name] = list(messages)

    def save(self, conversation_name: str, write_backup: bool = True) -> None:
        self.saved.append(conversation_name)

    def search(
        self,
        keyword: str,
        include_delegated: bool = True,
        include_empty: bool = True,
    ) -> list[str]:
        return []


def test_copy_conversation_stores_the_messages_under_the_new_name():
    stored = _messages(2)
    manager = _MemoryHistoryManager({"old": stored})

    copy_conversation(manager, "old", "new")

    assert manager.conversations["new"] == stored
    assert manager.conversations["old"] == stored
    assert manager.saved == ["new"]


def test_copy_conversation_overwrites_the_target():
    """`/save` under an existing name replaces what was there."""
    manager = _MemoryHistoryManager({"old": _messages(1), "new": _messages(3)})

    copy_conversation(manager, "old", "new")

    assert len(manager.conversations["new"]) == 1


def test_copy_conversation_of_a_missing_source_stores_an_empty_one():
    """A source that was never written copies as empty, not as an error."""
    manager = _MemoryHistoryManager()

    copy_conversation(manager, "absent", "new")

    assert manager.conversations["new"] == []
    assert manager.saved == ["new"]


def test_truncate_conversation_drops_everything_past_keep():
    stored = _messages(3)
    manager = _MemoryHistoryManager({"conv": stored})

    truncate_conversation(manager, "conv", 2)

    assert manager.conversations["conv"] == stored[:2]
    assert manager.saved == ["conv"]


def test_truncate_conversation_leaves_a_short_conversation_alone():
    """A conversation already that short is not written back."""
    stored = _messages(2)
    manager = _MemoryHistoryManager({"conv": stored})

    truncate_conversation(manager, "conv", 2)

    assert manager.conversations["conv"] == stored
    assert manager.saved == []


def test_truncate_conversation_never_grows_a_conversation():
    """`keep` past the end must not pad the store with nothing."""
    stored = _messages(1)
    manager = _MemoryHistoryManager({"conv": stored})

    truncate_conversation(manager, "conv", 5)

    assert manager.conversations["conv"] == stored
    assert manager.saved == []
