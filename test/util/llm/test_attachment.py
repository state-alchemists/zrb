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
