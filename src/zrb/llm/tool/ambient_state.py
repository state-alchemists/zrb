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

# `ask.py` and `worktree.py` set these, but neither owns them: both declare
# tool signatures and so import `pydantic`, while `live_context.py` reads this
# state on the eager `import zrb` path. Storing them in this module — which
# imports nothing heavier than `contextvars` — keeps that read from pulling
# pydantic's machinery (~55ms) into every CLI invocation.
active_worktree: ContextVar[str] = ContextVar("zrb_active_worktree", default="")

interactive_mode: ContextVar[bool] = ContextVar("zrb_interactive_mode", default=True)


def get_interactive_mode() -> bool:
    """Return whether the current chat session is interactive."""
    return interactive_mode.get()


def set_interactive_mode(value: bool) -> None:
    """Set the interactive flag for the current chat session."""
    interactive_mode.set(value)


_current_session: ContextVar[str] = ContextVar("zrb_current_session", default="default")

# The display session name is a client label and not unique, so it is never
# an ownership key. This carries `ChatSessionManager`'s unique dict key, bound
# per message in `chat_session_runner.py`; `shell_background.py` tags
# background processes with it so removing one session can't touch another's.
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
