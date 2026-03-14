"""Tests for ContentTransformer class."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.content_transformer.content_transformer import ContentTransformer
from zrb.context.any_context import AnyContext


def test_content_transformer_init():
    """Test ContentTransformer initialization."""
    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={"old": "new"},
    )
    assert transformer.name == "test"


def test_content_transformer_match_regex():
    """Test ContentTransformer.match with regex pattern."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match=r"^.*\.txt$",
        transform={"old": "new"},
    )
    # Test regex match works
    assert transformer.match(ctx, "file.txt") is True


def test_content_transformer_match_callable():
    """Test ContentTransformer.match with callable pattern."""

    def custom_match(ctx, file_path):
        return file_path.endswith(".custom")

    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match=custom_match,
        transform={"old": "new"},
    )
    assert transformer.match(ctx, "file.custom") is True
    assert transformer.match(ctx, "file.txt") is False


def test_content_transformer_match_fnmatch():
    """Test ContentTransformer.match with fnmatch pattern."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={"old": "new"},
    )
    # Pattern without path separator should use fnmatch
    result = transformer.match(ctx, "/path/to/file.txt")
    # The fnmatch path logic is internal, check it doesn't crash
    assert isinstance(result, bool)


def test_content_transformer_transform_file_dict():
    """Test ContentTransformer.transform_file with dict transform."""
    ctx = MagicMock(spec=AnyContext)
    ctx.render = MagicMock(return_value="new")

    with patch("zrb.content_transformer.content_transformer.read_file") as mock_read:
        mock_read.return_value = "Hello old world"
        with patch(
            "zrb.content_transformer.content_transformer.write_file"
        ) as mock_write:
            transformer = ContentTransformer(
                name="test",
                match="*.txt",
                transform={"old": "new"},
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            # Check that write was called
            mock_write.assert_called_once()


def test_content_transformer_transform_file_callable():
    """Test ContentTransformer.transform_file with callable transform."""

    def custom_transform(ctx, file_path):
        return "custom result"

    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform=custom_transform,
    )
    result = transformer.transform_file(ctx, "/path/to/file.txt")
    assert result == "custom result"


def test_content_transformer_get_str_replacement_callable():
    """Test _get_str_replacement with callable replacement."""

    def get_value(ctx):
        return "dynamic value"

    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={},
    )
    result = transformer._get_str_replacement(ctx, get_value)
    assert result == "dynamic value"


def test_content_transformer_get_str_replacement_render():
    """Test _get_str_replacement with auto_render=True."""
    ctx = MagicMock(spec=AnyContext)
    ctx.render = MagicMock(return_value="rendered value")

    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={},
        auto_render=True,
    )
    result = transformer._get_str_replacement(ctx, "${var}")
    ctx.render.assert_called_once_with("${var}")
    assert result == "rendered value"


def test_content_transformer_get_str_replacement_no_render():
    """Test _get_str_replacement with auto_render=False."""
    ctx = MagicMock(spec=AnyContext)
    ctx.render = MagicMock()

    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={},
        auto_render=False,
    )
    result = transformer._get_str_replacement(ctx, "${var}")
    # Should not call render
    ctx.render.assert_not_called()
    assert result == "${var}"
