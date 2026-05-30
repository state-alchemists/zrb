import os
from unittest.mock import MagicMock

import pytest

from zrb.llm.util.attachment import (
    get_attachments,
    get_media_type,
    normalize_attachments,
)


def test_get_media_type():
    assert get_media_type("test.png") == "image/png"
    assert get_media_type("test.jpg") == "image/jpeg"
    assert get_media_type("test.pdf") == "application/pdf"
    assert get_media_type("test.unknown") is None
    assert get_media_type("test") is None


def test_get_attachments_none():
    ctx = MagicMock()
    assert get_attachments(ctx, None) == []


def test_get_attachments_single():
    ctx = MagicMock()
    assert get_attachments(ctx, "path/to/file") == ["path/to/file"]


def test_get_attachments_list():
    ctx = MagicMock()
    assert get_attachments(ctx, ["f1", "f2"]) == ["f1", "f2"]


def test_get_attachments_callable():
    ctx = MagicMock()
    callback = lambda c: ["f1", "f2"]
    assert get_attachments(ctx, callback) == ["f1", "f2"]


def test_normalize_attachments_string_path(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")

    # We need to mock BinaryContent because pydantic_ai might not be fully available or needed for simple check
    from pydantic_ai import BinaryContent

    normalized = normalize_attachments([str(f)])
    assert len(normalized) == 1
    assert isinstance(normalized[0], BinaryContent)
    assert normalized[0].media_type == "text/plain"
    assert normalized[0].data == b"hello"


def test_normalize_attachments_already_normalized():
    item = MagicMock()
    normalized = normalize_attachments([item])
    assert normalized == [item]


def test_get_attachments_callable_returns_none():
    """Line 55: callable returning None should return empty list."""
    ctx = MagicMock()
    callback = lambda c: None
    assert get_attachments(ctx, callback) == []


def test_get_attachments_callable_returns_single_item():
    """Line 58: callable returning single non-list item should wrap it."""
    ctx = MagicMock()
    callback = lambda c: "single_item"
    assert get_attachments(ctx, callback) == ["single_item"]


def test_normalize_attachments_none_item():
    """Line 22: None items in the list should be skipped."""
    result = normalize_attachments([None, "not_a_real_file.txt"])
    # None is skipped, file path doesn't exist so nothing added
    assert result == []


def test_normalize_attachments_file_not_found(capsys):
    """Line 34: File not found should print warning."""
    normalize_attachments(["/nonexistent/path/file.txt"])
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_normalize_attachments_unknown_media_type(tmp_path, capsys):
    """Line 37-38: Unknown media type should print warning."""
    f = tmp_path / "test.xyz"
    f.write_text("data")
    normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "Unknown media type" in captured.out


def test_normalize_attachments_read_error(tmp_path, capsys):
    """Line 31-32: File read error should be caught and printed."""
    from unittest.mock import patch

    f = tmp_path / "test.txt"
    f.write_text("hello")

    def mock_read_bytes(*args, **kwargs):
        raise PermissionError("access denied")

    with patch("pathlib.Path.read_bytes", side_effect=mock_read_bytes):
        normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))

    captured = capsys.readouterr()
    assert "Failed to read" in captured.out or "access denied" in captured.out


def test_normalize_attachments_non_string_item():
    """Line 39-40: Non-string, already valid items are passed through."""
    from pydantic_ai import BinaryContent

    item = BinaryContent(data=b"test", media_type="text/plain")
    result = normalize_attachments([item])
    assert len(result) == 1
    assert result[0] is item
