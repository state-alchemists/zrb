"""Ambient state for tool calls — active worktree, current tool session."""

from __future__ import annotations

from contextvars import ContextVar

from zrb.llm.input_source import InputProvenance

# Declared here, not in `ask.py`/`worktree.py`, so `live_context.py` can read
# them on the `import zrb` path without loading pydantic (~55ms).
active_worktree: ContextVar[str] = ContextVar("zrb_active_worktree", default="")

interactive_mode: ContextVar[bool] = ContextVar("zrb_interactive_mode", default=True)

input_provenance: ContextVar[InputProvenance | None] = ContextVar(
    "zrb_input_provenance", default=None
)


def get_interactive_mode() -> bool:
    """Return whether the current chat session is interactive."""
    return interactive_mode.get()


def set_interactive_mode(value: bool) -> None:
    """Set the interactive flag for the current chat session."""
    interactive_mode.set(value)


def get_input_provenance() -> InputProvenance | None:
    """Return the source of the current user turn, when one is known."""
    return input_provenance.get()


def set_input_provenance(value: InputProvenance | None) -> None:
    """Set the source of the current user turn."""
    input_provenance.set(value)


_current_session: ContextVar[str] = ContextVar("zrb_current_session", default="default")

# `ChatSessionManager`'s unique session key (the display name is not unique),
# bound per message in `chat_session_runner.py`.
current_chat_session_id: ContextVar[str] = ContextVar(
    "zrb_current_chat_session_id", default=""
)


def get_current_chat_session_id() -> str:
    """The owning `ChatSessionManager` session_id, or "" outside a chat run."""
    return current_chat_session_id.get()


def get_session_ownership_key(display_name: str = "") -> str:
    """The chat session ID, falling back to *display_name* outside web chat."""
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
    """Set the session name that tool calls should default to."""
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
    "get_input_provenance",
    "set_input_provenance",
    "current_chat_session_id",
    "get_current_chat_session_id",
    "get_session_ownership_key",
]
