"""Ambient state for tool calls — active worktree, current tool session.

These `ContextVar`s are set by tools like `EnterWorktree` or by the prompt
middleware, and read by other tools (e.g. `Shell`, `DelegateToAgent`, the todo
tools) that need to know "what worktree are we in" or "which session's todos".

The underlying `ContextVar`s stay where their owning tools define them. This
module gives callers one place to look up "what tool-scoped ambient state
exists" without chasing imports across tool modules.
"""

from __future__ import annotations

from contextvars import ContextVar

from zrb.llm.tool.ask import (
    get_interactive_mode,
    interactive_mode,
    set_interactive_mode,
)
from zrb.llm.tool.worktree import active_worktree

_current_session: ContextVar[str] = ContextVar("zrb_current_session", default="default")

# The *display* session name (see `get_current_tool_session` below) is a
# client-supplied label — `ChatSessionManager.create_session` never enforces
# it is unique, so it must never be used as a resource-ownership key (two
# concurrent chat sessions can share one). `current_chat_session_id` instead
# carries `ChatSessionManager`'s own dict key, which *is* unique by
# construction — bound once per message drive in `chat_session_runner.py`,
# read by `shell_background.py` to tag which chat session owns a background
# process, so removing one session can never reach into another's.
current_chat_session_id: ContextVar[str] = ContextVar(
    "zrb_current_chat_session_id", default=""
)


def get_current_chat_session_id() -> str:
    """The owning `ChatSessionManager` session_id, or "" outside a chat run."""
    return current_chat_session_id.get()


def get_session_ownership_key(display_name: str = "") -> str:
    """Return the stable resource key, falling back for standalone CLI UIs.

    Web chat binds the opaque manager ID for the lifetime of its driver task.
    The interactive CLI has no ``ChatSessionManager`` ID, so its display name
    remains the compatible fallback there.
    """
    return get_current_chat_session_id() or display_name or "default"


def get_current_context_session() -> str:
    """Get the current session name, set by set_current_session() before agent runs."""
    return _current_session.get()


def set_current_session(session_name: str) -> None:
    """Set the current session name so todo tools use the right session automatically."""
    if session_name:
        _current_session.set(session_name)


def get_active_worktree() -> str:
    """Return the active worktree path, or empty string if no worktree is active."""
    return active_worktree.get()


def set_active_worktree(path: str) -> None:
    """Set or clear (pass "") the active worktree path."""
    active_worktree.set(path)


def get_current_tool_session() -> str:
    """Return the session name that tool calls should default to."""
    return get_current_context_session()


def set_current_tool_session(session_name: str) -> None:
    """Set the session name that tool calls should default to.

    Preferred over the `set_current_session` alias for readability.
    """
    set_current_session(session_name)


__all__ = [
    "active_worktree",
    "interactive_mode",
    "get_active_worktree",
    "set_active_worktree",
    "get_current_tool_session",
    "set_current_tool_session",
    "get_current_context_session",
    "set_current_session",
    "get_interactive_mode",
    "set_interactive_mode",
    "current_chat_session_id",
    "get_current_chat_session_id",
    "get_session_ownership_key",
]
