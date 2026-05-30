"""Tests for the `zrb.contextvars` discoverability index module."""

from __future__ import annotations

from zrb import contextvars as cv


def test_index_exports_all_wrappers():
    # If a wrapper is missing here, contributors will silently lose discoverability.
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
        "active_worktree",
        "get_active_worktree",
        "set_active_worktree",
        "get_current_tool_session",
        "set_current_tool_session",
    }
    missing = expected - set(cv.__all__)
    assert not missing, f"Missing from contextvars.__all__: {sorted(missing)}"
    for name in expected:
        assert hasattr(cv, name), f"`zrb.contextvars.{name}` should be importable"


def test_index_does_not_create_independent_state():
    """The index re-exports — it must not create a parallel ContextVar."""
    from zrb.llm.agent.run.runtime_state import current_ui as direct_var

    assert cv.current_ui is direct_var

    from zrb.llm.tool.worktree import active_worktree as direct_worktree

    assert cv.active_worktree is direct_worktree


def test_index_get_set_active_worktree_round_trip():
    cv.set_active_worktree("/tmp/index-test")
    try:
        assert cv.get_active_worktree() == "/tmp/index-test"
    finally:
        cv.set_active_worktree("")
