"""Tests for tool ambient-state wrappers (zrb.llm.tool.ambient_state)."""

from __future__ import annotations

from zrb.llm.tool.ambient_state import (
    set_current_session,  # legacy alias kept for back-compat
)
from zrb.llm.tool.ambient_state import (
    active_worktree,
    get_active_worktree,
    get_current_tool_session,
    set_active_worktree,
    set_current_tool_session,
)


def test_active_worktree_default_is_empty():
    # When no worktree is active, the wrapper returns an empty string.
    set_active_worktree("")
    try:
        assert get_active_worktree() == ""
    finally:
        set_active_worktree("")


def test_set_and_get_active_worktree_round_trip():
    set_active_worktree("/tmp/zrb-worktree-test")
    try:
        assert get_active_worktree() == "/tmp/zrb-worktree-test"
        # Underlying ContextVar reflects the same value.
        assert active_worktree.get() == "/tmp/zrb-worktree-test"
    finally:
        set_active_worktree("")
    assert get_active_worktree() == ""


def test_current_tool_session_set_and_get():
    set_current_tool_session("alpha-session")
    try:
        assert get_current_tool_session() == "alpha-session"
    finally:
        set_current_tool_session("default")


def test_legacy_set_current_session_alias_still_works():
    """Existing callers of `set_current_session` must keep working unchanged."""
    set_current_session("legacy-session")
    try:
        assert get_current_tool_session() == "legacy-session"
    finally:
        set_current_tool_session("default")


def test_setting_empty_session_is_a_no_op():
    """The original semantics: empty session must not overwrite the active one."""
    set_current_tool_session("preserved")
    try:
        # Empty string should NOT change the current value (matches plan.set_current_session).
        set_current_tool_session("")
        assert get_current_tool_session() == "preserved"
    finally:
        set_current_tool_session("default")
