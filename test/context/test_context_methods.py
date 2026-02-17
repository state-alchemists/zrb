import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_shared_context import AnySharedContext
from zrb.context.context import Context
from zrb.dot_dict.dot_dict import DotDict


@pytest.fixture
def mock_shared_ctx():
    shared = MagicMock(spec=AnySharedContext)
    shared.env = DotDict()
    shared.render.side_effect = lambda template: str(template)
    shared.get_logging_level.return_value = logging.DEBUG
    shared.session = None
    return shared


def test_context_init(mock_shared_ctx):
    ctx = Context(mock_shared_ctx, "task1", 32, "icon")
    assert repr(ctx) == f"<Context shared_ctx={mock_shared_ctx}>"


def test_render_types(mock_shared_ctx):
    mock_shared_ctx.render.side_effect = lambda template: template
    ctx = Context(mock_shared_ctx, "task1", 32, "icon")

    assert ctx.render_bool(True) is True
    assert ctx.render_bool("true") is True
    assert ctx.render_bool("false") is False
    assert ctx.render_int(123) == 123
    assert ctx.render_int("123") == 123
    assert ctx.render_float(12.34) == 12.34
    assert ctx.render_float(10) == 10.0
    assert ctx.render_float("12.34") == 12.34


def test_update_task_env(mock_shared_ctx):
    ctx = Context(mock_shared_ctx, "task1", 32, "icon")
    ctx.update_task_env({"NEW_VAR": "val"})
    assert ctx.env["NEW_VAR"] == "val"


def test_logging_methods(mock_shared_ctx):
    ctx = Context(mock_shared_ctx, "task1", 32, "icon")

    # Print plain
    ctx.print("Hello", plain=True)
    mock_shared_ctx.append_to_shared_log.assert_called()
    assert "Hello" in mock_shared_ctx.append_to_shared_log.call_args[0][0]

    # Reset mock
    mock_shared_ctx.append_to_shared_log.reset_mock()

    # Print styled
    ctx.print("HelloStyled")
    mock_shared_ctx.append_to_shared_log.assert_called()
    log_msg = mock_shared_ctx.append_to_shared_log.call_args[0][0]
    assert "HelloStyled" in log_msg
    assert "task1" in log_msg

    # Log levels
    mock_shared_ctx.get_logging_level.return_value = logging.DEBUG

    for method, level_name in [
        (ctx.log_debug, "DEBUG"),
        (ctx.log_info, "INFO"),
        (ctx.log_warning, "WARNING"),
        (ctx.log_error, "ERROR"),
        (ctx.log_critical, "CRITICAL"),
    ]:
        mock_shared_ctx.append_to_shared_log.reset_mock()
        method(f"{level_name} msg")
        mock_shared_ctx.append_to_shared_log.assert_called()
        assert (
            f"{level_name} msg" in mock_shared_ctx.append_to_shared_log.call_args[0][0]
        )


def test_logging_level_filtering(mock_shared_ctx):
    ctx = Context(mock_shared_ctx, "task1", 32, "icon")
    mock_shared_ctx.get_logging_level.return_value = logging.ERROR

    mock_shared_ctx.append_to_shared_log.reset_mock()
    ctx.log_info("should not print")
    mock_shared_ctx.append_to_shared_log.assert_not_called()

    ctx.log_error("should print")
    mock_shared_ctx.append_to_shared_log.assert_called()
