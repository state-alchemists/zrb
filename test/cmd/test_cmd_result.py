"""Tests for CmdResult class."""

from zrb.cmd.cmd_result import CmdResult


def test_cmd_result_init():
    """Test CmdResult initialization."""
    result = CmdResult("output", "error", "display")
    assert result.output == "output"
    assert result.error == "error"
    assert result.display == "display"


def test_cmd_result_str():
    """Test CmdResult __str__ returns output."""
    result = CmdResult("test output", "test error", "test display")
    assert str(result) == "test output"


def test_cmd_result_repr():
    """Test CmdResult __repr__ shows last line of output and error."""
    result = CmdResult("line1\nline2\nlast_output", "err1\nerr2\nlast_error", "display")
    repr_str = repr(result)
    assert "CmdResult" in repr_str
    assert "last_output" in repr_str
    assert "last_error" in repr_str


def test_cmd_result_repr_empty_output():
    """Test CmdResult __repr__ with empty output."""
    result = CmdResult("", "error", "display")
    repr_str = repr(result)
    assert "<CmdResult" in repr_str


def test_cmd_result_repr_empty_error():
    """Test CmdResult __repr__ with empty error."""
    result = CmdResult("output", "", "display")
    repr_str = repr(result)
    assert "<CmdResult" in repr_str


def test_cmd_result_repr_both_empty():
    """Test CmdResult __repr__ with empty output and error."""
    result = CmdResult("", "", "display")
    repr_str = repr(result)
    assert "<CmdResult" in repr_str


def test_cmd_result_single_line():
    """Test CmdResult with single line output."""
    result = CmdResult("single line", "error msg", "display")
    repr_str = repr(result)
    assert "single line" in repr_str
