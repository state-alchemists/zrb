"""Tests for the `zrb.contextvars` discoverability index module."""

from __future__ import annotations

from zrb import contextvars as cv


def test_index_exports_all_wrappers():
    # Exact-match, not subset: a wrapper missing here means contributors
    # silently lose discoverability, but the reverse drift (a real export
    # this set doesn't know about) is just as real a gap and a subset check
    # can never catch it. Update this set in the same diff that adds,
    # removes, or renames a ContextVar export in `zrb.contextvars`.
    expected = {
        "current_ctx",
        "get_current_ctx",
        "zrb_print",
        "current_ui",
        "current_tool_confirmation",
        "current_yolo",
        "current_approval_channel",
        "get_current_ui",
        "get_current_tool_confirmation",
        "get_current_yolo",
        "get_current_approval_channel",
        "current_sandbox_policy",
        "get_current_sandbox_policy",
        "sandbox_policy",
        "active_worktree",
        "get_active_worktree",
        "set_active_worktree",
        "get_current_tool_session",
        "set_current_tool_session",
        "current_hook_manager",
        "get_current_hook_manager",
        "current_agent_run_scope",
        "get_current_agent_run_scope",
        "current_permission_policy",
        "get_current_permission_policy",
        "permission_policy",
        "current_agent_mode",
        "get_current_agent_mode",
        "set_current_agent_mode",
        "get_current_context_session",
        "set_current_session",
        "interactive_mode",
        "get_interactive_mode",
        "set_interactive_mode",
        "current_chat_session_id",
        "get_current_chat_session_id",
        "get_session_ownership_key",
    }
    actual = set(cv.__all__)
    assert actual == expected, (
        "zrb.contextvars.__all__ drifted from this test's `expected` set — "
        "a ContextVar export was added, removed, or renamed. Update "
        "`expected` here to match, in the same diff.\n"
        f"missing from __all__={sorted(expected - actual)}\n"
        f"extra in __all__={sorted(actual - expected)}"
    )
    for name in expected:
        assert hasattr(cv, name), f"`zrb.contextvars.{name}` should be importable"


def test_index_does_not_create_independent_state():
    """The index re-exports — it must not create a parallel ContextVar."""
    from zrb.llm.agent_state import current_ui as direct_var

    assert cv.current_ui is direct_var

    from zrb.llm.tool.worktree import active_worktree as direct_worktree

    assert cv.active_worktree is direct_worktree


def test_index_get_set_active_worktree_round_trip():
    cv.set_active_worktree("/tmp/index-test")
    try:
        assert cv.get_active_worktree() == "/tmp/index-test"
    finally:
        cv.set_active_worktree("")
