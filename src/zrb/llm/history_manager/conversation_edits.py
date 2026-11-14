"""Changing a conversation that is already stored.

`/save` keeps the live conversation under a new name, and `/rewind` drops the
messages a restored snapshot did not have. Both are one shape — read the stored
messages, write a different set back — and both were spelled out inline in the
slash-command handlers, which made two UI commands the authority on how a
conversation is written.

The operations live here, beside the store and its naming, so anything that
holds a history manager can copy or truncate without reaching up into another
layer. Nothing here knows about a task, a session or a UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


def copy_conversation(
    history_manager: "AnyHistoryManager", source: str, target: str
) -> None:
    """Store *source*'s messages under *target* too, leaving *source* in place.

    *target* is overwritten. What `/save` does with the running conversation.
    """
    history_manager.update(target, history_manager.load(source))
    history_manager.save(target)


def truncate_conversation(
    history_manager: "AnyHistoryManager", conversation_name: str, keep: int
) -> None:
    """Drop every message of *conversation_name* past the first *keep*.

    Never grows a conversation: a stored one already that short is left alone.
    What `/rewind` does with the message count its snapshot recorded.
    """
    messages = history_manager.load(conversation_name)
    if len(messages) <= keep:
        return
    history_manager.update(conversation_name, messages[:keep])
    history_manager.save(conversation_name)
