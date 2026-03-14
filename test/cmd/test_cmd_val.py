"""Tests for CmdVal classes."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.cmd.cmd_val import AnyCmdVal, Cmd, CmdPath
from zrb.context.context import Context


def test_cmd_to_str():
    """Test Cmd.to_str returns command string."""
    ctx = MagicMock(spec=Context)
    ctx.input = {}

    with patch("zrb.cmd.cmd_val.get_str_attr") as mock_get_str_attr:
        mock_get_str_attr.return_value = "echo hello"
        cmd = Cmd("echo hello")
        result = cmd.to_str(ctx)
        assert result == "echo hello"


def test_cmd_to_str_with_auto_render():
    """Test Cmd.to_str with auto_render=False."""
    ctx = MagicMock(spec=Context)
    ctx.input = {}

    with patch("zrb.cmd.cmd_val.get_str_attr") as mock_get_str_attr:
        mock_get_str_attr.return_value = "echo hello"
        cmd = Cmd("echo hello", auto_render=False)
        result = cmd.to_str(ctx)
        assert result == "echo hello"


def test_cmd_path_to_str():
    """Test CmdPath.to_str reads file content."""
    ctx = MagicMock(spec=Context)
    ctx.input = {}

    with patch("zrb.cmd.cmd_val.read_file") as mock_read_file:
        mock_read_file.return_value = "file content"
        cmd_path = CmdPath("/path/to/file")
        result = cmd_path.to_str(ctx)
        assert result == "file content"
        mock_read_file.assert_called_once()


def test_cmd_path_with_auto_render():
    """Test CmdPath with auto_render=False."""
    ctx = MagicMock(spec=Context)
    ctx.input = {}

    with patch("zrb.cmd.cmd_val.read_file") as mock_read_file:
        mock_read_file.return_value = "content"
        cmd_path = CmdPath("/path/to/file", auto_render=False)
        result = cmd_path.to_str(ctx)
        assert result == "content"


def test_any_cmd_val_is_abstract():
    """Test AnyCmdVal is abstract and cannot be instantiated directly."""
    ctx = MagicMock(spec=Context)

    # AnyCmdVal should not be directly instantiable
    with pytest.raises(TypeError):
        AnyCmdVal()


def test_cmd_inherits_from_any_cmd_val():
    """Test Cmd is a subclass of AnyCmdVal."""
    cmd = Cmd("test")
    assert isinstance(cmd, AnyCmdVal)


def test_cmd_path_inherits_from_any_cmd_val():
    """Test CmdPath is a subclass of AnyCmdVal."""
    with patch("zrb.cmd.cmd_val.read_file"):
        cmd_path = CmdPath("/path")
        assert isinstance(cmd_path, AnyCmdVal)
