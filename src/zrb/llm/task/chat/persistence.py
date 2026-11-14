"""Where a chat session's conversation is kept.

The task holds two knobs — a history manager and a conversation name — and the
inner `LLMTask` cannot run without them resolved. Working out what they are for
the run that is starting, and putting a stored conversation back on screen when
a session resumes, is this module's whole job.

Editing a conversation that already exists is not here: copying and truncating
take nothing but a manager, so they live beside the store, in
`zrb.llm.history_manager.conversation_edits`. The split is the import direction,
not taste — a UI reaches for those two, and it cannot reach into this package
without the two pointing at each other.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from zrb.attr.tpl import Tpl
from zrb.config.config import CFG
from zrb.llm.history_manager.file_history_manager import default_history_manager

if TYPE_CHECKING:
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.history_config import HistoryConfig
    from zrb.llm.ui.any_ui import AnyUI


def resolve_history_manager(task: "LLMChatTask") -> "AnyHistoryManager":
    """The task's manager, or the default file-backed store."""
    manager = task.history_manager
    return default_history_manager() if manager is None else manager


def build_session_history_config(
    task: "LLMChatTask", history_manager: "AnyHistoryManager"
) -> "HistoryConfig":
    """The task's history knobs, with *history_manager* and the live session.

    The inner task's conversation is always the active chat session, and
    `/save` can rename that session mid-run, so the name stays a `Tpl` read per
    request rather than a string captured here.
    """
    return replace(
        task.history_config,
        history_manager=history_manager,
        conversation_name=Tpl("{ctx.input.session}"),
    )


def replay_conversation(
    ui: "AnyUI", history_manager: "AnyHistoryManager", conversation_name: str
) -> None:
    """Put a stored conversation on screen; a missing one is not an error.

    The UI replays it through `replay_history`; a UI that does not override that
    writes a plain text dump.
    """
    if not conversation_name:
        return
    try:
        history = history_manager.load(conversation_name)
        if not history:
            return
        ui.display.replay_history(history)
    except FileNotFoundError:
        pass
    except Exception as e:
        CFG.LOGGER.warning(f"Failed to load history for session {conversation_name}: {e}")
