import os
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.util.attachment import (
    check_attachment_bytes,
    get_attachments,
    get_media_type,
    get_oversized_by,
    normalize_attachments,
    sniff_mismatch,
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


def test_normalize_attachments_directory_not_found(tmp_path, capsys):
    normalize_attachments([str(tmp_path)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_get_oversized_by_under_limit(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("hello")
    assert get_oversized_by(str(f)) is None


def test_get_oversized_by_over_limit(tmp_path, monkeypatch):
    f = tmp_path / "small.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 2)
    actual, limit = get_oversized_by(str(f))
    assert actual == 5
    assert limit == 2


def test_get_oversized_by_disabled(tmp_path, monkeypatch):
    f = tmp_path / "small.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 0)
    assert get_oversized_by(str(f)) is None


def test_normalize_attachments_oversized(tmp_path, capsys, monkeypatch):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 1)
    normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "too large" in captured.out


def test_sniff_mismatch_png_ok():
    assert sniff_mismatch(b"\x89PNG\r\n\x1a\n" + b"rest", "image/png") is None


def test_sniff_mismatch_png_spoofed():
    assert sniff_mismatch(b"not a png", "image/png") is not None


def test_sniff_mismatch_webp_ok():
    data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP"
    assert sniff_mismatch(data, "image/webp") is None


def test_sniff_mismatch_webp_bad():
    assert sniff_mismatch(b"RIFFxxxxNOPE", "image/webp") is not None


def test_sniff_mismatch_no_signature_for_type():
    """Types without a known signature (e.g. audio) are never flagged."""
    assert sniff_mismatch(b"anything", "audio/mpeg") is None


def test_normalize_attachments_spoofed_extension(tmp_path, capsys):
    f = tmp_path / "fake.png"
    f.write_bytes(b"not actually a png")
    normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "doesn't look like" in captured.out


def test_check_attachment_bytes_ok():
    data = b"\x89PNG\r\n\x1a\n" + b"rest"
    assert check_attachment_bytes(data, "image/png") is None


def test_check_attachment_bytes_oversized(monkeypatch):
    data = b"\x89PNG\r\n\x1a\n" + b"rest"
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 2)
    reason = check_attachment_bytes(data, "image/png")
    assert reason is not None
    assert "too large" in reason


def test_check_attachment_bytes_spoofed():
    reason = check_attachment_bytes(b"not a png", "image/png")
    assert reason is not None
    assert "doesn't look like" in reason
