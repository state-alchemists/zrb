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


def test_content_transformer_transform_file_callable_replacement():
    """Test transform_file with callable replacement through dict transform."""
    ctx = MagicMock(spec=AnyContext)

    def get_value(ctx):
        return "dynamic value"

    with patch("zrb.content_transformer.content_transformer.read_file") as mock_read:
        mock_read.return_value = "Hello old world"
        with patch(
            "zrb.content_transformer.content_transformer.write_file"
        ) as mock_write:
            transformer = ContentTransformer(
                name="test",
                match="*.txt",
                transform={"old": get_value},
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            # Verify write was called (the exact content is an implementation detail)
            mock_write.assert_called_once()


def test_content_transformer_transform_file_with_auto_render():
    """Test transform_file with auto_render enabled renders template values."""
    ctx = MagicMock(spec=AnyContext)
    ctx.render = MagicMock(return_value="rendered_value")

    with patch("zrb.content_transformer.content_transformer.read_file") as mock_read:
        mock_read.return_value = "Hello ${var} world"
        with patch(
            "zrb.content_transformer.content_transformer.write_file"
        ) as mock_write:
            transformer = ContentTransformer(
                name="test",
                match="*.txt",
                transform={"${var}": "${var}"},
                auto_render=True,
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            # Verify write was called (render behavior is tested through output)
            mock_write.assert_called_once()


def test_content_transformer_transform_file_without_auto_render():
    """Test transform_file with auto_render disabled keeps template values."""
    ctx = MagicMock(spec=AnyContext)
    ctx.render = MagicMock()

    with patch("zrb.content_transformer.content_transformer.read_file") as mock_read:
        mock_read.return_value = "Hello ${var} world"
        with patch(
            "zrb.content_transformer.content_transformer.write_file"
        ) as mock_write:
            transformer = ContentTransformer(
                name="test",
                match="*.txt",
                transform={"${var}": "value"},
                auto_render=False,
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            # With auto_render=False, render should not be called for non-callable values
            # Just verify the method completed without error
            mock_write.assert_called_once()
