"""Tests for context/shared_context.py — covers the unwatched edges."""

from unittest.mock import MagicMock, patch

from zrb.context.shared_context import SharedContext


def test_repr_uses_class_name():
    ctx = SharedContext()
    assert repr(ctx) == "<SharedContext>"


def test_is_web_mode_reflects_constructor_flag():
    assert SharedContext(is_web_mode=True).is_web_mode is True
    assert SharedContext(is_web_mode=False).is_web_mode is False


def test_is_tty_falls_back_to_false_on_exception():
    """If sys.stdin.isatty() raises (closed stdin, weird env) the guard returns False."""
    ctx = SharedContext()
    with patch("zrb.context.shared_context.sys") as mock_sys:
        mock_sys.stdin.isatty.side_effect = ValueError("I/O detached")
        assert ctx.is_tty is False


def test_append_to_shared_log_propagates_to_parent_session():
    parent_ctx = SharedContext()
    parent_session = MagicMock()
    parent_session.shared_ctx = parent_ctx
    parent_session.parent = None

    child_ctx = SharedContext()
    child_session = MagicMock()
    child_session.shared_ctx = child_ctx
    child_session.parent = parent_session

    child_ctx.set_session(child_session)
    child_ctx.append_to_shared_log("hello")
    assert "hello" in child_ctx.shared_log
    assert "hello" in parent_ctx.shared_log


def test_append_to_shared_log_no_parent_only_records_local():
    ctx = SharedContext()
    session = MagicMock()
    session.shared_ctx = ctx
    session.parent = None
    ctx.set_session(session)
    ctx.append_to_shared_log("solo")
    assert ctx.shared_log == ["solo"]
