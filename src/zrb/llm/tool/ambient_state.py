"""Ambient state for tool calls — active worktree, current tool session.

These `ContextVar`s are set by tools like `EnterWorktree` or by the prompt
middleware, and read by other tools (e.g. `Bash`, `DelegateToAgent`, the todo
tools) that need to know "what worktree are we in" or "which session's todos".

The underlying `ContextVar`s stay where their owning tools define them. This
module gives callers one place to look up "what tool-scoped ambient state
exists" without chasing imports across tool modules.
"""

from __future__ import annotations

from zrb.llm.tool.plan import (
    _current_session,
    get_current_context_session,
    set_current_session,
)
from zrb.llm.tool.worktree import active_worktree


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

    Preferred over the legacy `set_current_session` alias for readability.
    """
    set_current_session(session_name)


__all__ = [
    "active_worktree",
    "_current_session",
    "get_active_worktree",
    "set_active_worktree",
    "get_current_tool_session",
    "set_current_tool_session",
    "get_current_context_session",
    "set_current_session",
]
