"""Tests for ContentTransformer class."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.attr.tpl import Tpl
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
    # Pattern without path separator should match against the basename.
    assert transformer.match(ctx, "/path/to/file.txt") is True


def test_content_transformer_match_fnmatch_respects_pattern():
    """A glob pattern must only match files it actually describes."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={"old": "new"},
    )
    # A .py file must NOT match a *.txt transformer (the old bug matched everything).
    assert transformer.match(ctx, "/path/to/file.py") is False
    assert transformer.match(ctx, "notes.txt") is True


def test_content_transformer_match_path_glob():
    """A pattern carrying a path separator matches the full path via fnmatch."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="src/*.py",
        transform={"old": "new"},
    )
    assert transformer.match(ctx, "src/main.py") is True
    assert transformer.match(ctx, "test/main.py") is False


def test_content_transformer_match_multiple_patterns():
    """All configured patterns are considered, not just the first."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match=["*.md", "*.rst"],
        transform={"old": "new"},
    )
    assert transformer.match(ctx, "readme.md") is True
    assert transformer.match(ctx, "readme.rst") is True
    assert transformer.match(ctx, "readme.txt") is False


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


def test_content_transformer_transform_file_renders_tpl_replacement():
    """A Tpl replacement is rendered against the context before substitution."""
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
                transform={"${var}": Tpl("{ctx.input.x}")},
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            ctx.render.assert_called_once_with("{ctx.input.x}")
            mock_write.assert_called_once_with(
                "/path/to/file.txt", "Hello rendered_value world"
            )


def test_content_transformer_match_auto_mode_regex_glob_collision():
    """Documents the known "auto" collision: a glob-shaped pattern that also
    happens to parse as valid regex is matched with regex semantics."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="config.json",
        transform={"old": "new"},
    )
    # Default match_mode="auto": "." is a regex wildcard, so this "looks like
    # a literal glob" pattern also matches a file it doesn't literally equal.
    assert transformer.match(ctx, "configXjson") is True
    assert transformer.match(ctx, "config.json") is True


def test_content_transformer_match_glob_mode_avoids_regex_collision():
    """match_mode="glob" skips the regex attempt, so the same pattern only
    matches its literal glob meaning."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="config.json",
        transform={"old": "new"},
        match_mode="glob",
    )
    assert transformer.match(ctx, "configXjson") is False
    assert transformer.match(ctx, "config.json") is True


def test_content_transformer_match_regex_mode_skips_glob_fallback():
    """match_mode="regex" never falls back to fnmatch, so an invalid-regex
    pattern (or one that just doesn't match as regex) never matches."""
    ctx = MagicMock(spec=AnyContext)
    transformer = ContentTransformer(
        name="test",
        match="*.txt",
        transform={"old": "new"},
        match_mode="regex",
    )
    # "*.txt" is not valid regex (nothing to repeat), so under regex-only mode
    # it can never match, unlike under "auto" or "glob".
    assert transformer.match(ctx, "notes.txt") is False


def test_content_transformer_transform_file_keeps_bare_string_literal():
    """A bare-string replacement is substituted verbatim, never rendered."""
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
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            ctx.render.assert_not_called()
            mock_write.assert_called_once_with("/path/to/file.txt", "Hello value world")


def test_transform_file_resolves_every_replacement_shape():
    """Each replacement resolves independently: bare string literal, `Tpl`
    rendered, callable called. A callable returning `None` coerces to `""` —
    it used to reach `str.replace` directly and raise `TypeError`.
    """
    ctx = MagicMock(spec=AnyContext)
    ctx.render.side_effect = lambda t: "rendered" if t == "{ctx.input.x}" else t

    with patch("zrb.content_transformer.content_transformer.read_file") as mock_read:
        mock_read.return_value = "A_LIT A_TPL A_FN A_NONE"
        with patch(
            "zrb.content_transformer.content_transformer.write_file"
        ) as mock_write:
            transformer = ContentTransformer(
                name="test",
                match="*.txt",
                transform={
                    "A_LIT": "{literal}",
                    "A_TPL": Tpl("{ctx.input.x}"),
                    "A_FN": lambda c: "from-fn",
                    "A_NONE": lambda c: None,
                },
            )
            transformer.transform_file(ctx, "/path/to/file.txt")

            mock_write.assert_called_once_with(
                "/path/to/file.txt", "{literal} rendered from-fn "
            )
