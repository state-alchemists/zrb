"""Tests for TextInput class."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_shared_context import AnySharedContext
from zrb.input.text_input import TextInput


def test_text_input_init():
    """Test TextInput initialization."""
    inp = TextInput(
        name="content",
        description="Enter content",
        default="default text",
    )
    assert inp.name == "content"
    assert inp.description == "Enter content"


def test_text_input_comment_start_python():
    """Test TextInput.comment_start for Python extension."""
    inp = TextInput(name="code", extension=".py")
    assert inp.comment_start == "# "


def test_text_input_comment_start_ruby():
    """Test TextInput.comment_start for Ruby extension."""
    inp = TextInput(name="code", extension=".rb")
    assert inp.comment_start == "# "


def test_text_input_comment_start_shell():
    """Test TextInput.comment_start for Shell extension."""
    inp = TextInput(name="code", extension=".sh")
    assert inp.comment_start == "# "


def test_text_input_comment_start_markdown():
    """Test TextInput.comment_start for Markdown extension."""
    inp = TextInput(name="doc", extension=".md")
    assert inp.comment_start == "<!-- "


def test_text_input_comment_start_html():
    """Test TextInput.comment_start for HTML extension."""
    inp = TextInput(name="doc", extension=".html")
    assert inp.comment_start == "<!-- "


def test_text_input_comment_start_default():
    """Test TextInput.comment_start for default extension."""
    inp = TextInput(name="code", extension=".txt")
    assert inp.comment_start == "//"


def test_text_input_comment_start_custom():
    """Test TextInput.comment_start with custom value."""
    inp = TextInput(name="code", comment_start="/* ")
    assert inp.comment_start == "/* "


def test_text_input_comment_end_markdown():
    """Test TextInput.comment_end for Markdown extension."""
    inp = TextInput(name="doc", extension=".md")
    assert inp.comment_end == " -->"


def test_text_input_comment_end_html():
    """Test TextInput.comment_end for HTML extension."""
    inp = TextInput(name="doc", extension=".html")
    assert inp.comment_end == " -->"


def test_text_input_comment_end_default():
    """Test TextInput.comment_end for default extension."""
    inp = TextInput(name="code", extension=".py")
    assert inp.comment_end == ""


def test_text_input_comment_end_custom():
    """Test TextInput.comment_end with custom value."""
    inp = TextInput(name="code", comment_end=" */")
    assert inp.comment_end == " */"


def test_text_input_editor_cmd_custom():
    """Test TextInput.editor_cmd with custom editor."""
    inp = TextInput(name="content", editor="vim")
    assert inp.editor_cmd == "vim"


def test_text_input_editor_cmd_from_cfg():
    """Test TextInput.editor_cmd from config."""
    with patch("zrb.input.text_input.CFG") as mock_cfg:
        mock_cfg.EDITOR = "nano"
        inp = TextInput(name="content")
        assert inp.editor_cmd == "nano"


def test_text_input_editor_cmd_none():
    """Test TextInput.editor_cmd returns None when no editor."""
    with patch("zrb.input.text_input.CFG") as mock_cfg:
        mock_cfg.EDITOR = ""
        inp = TextInput(name="content")
        assert inp.editor_cmd is None


def test_text_input_to_html():
    """Test TextInput.to_html generates correct HTML."""
    inp = TextInput(name="content", description="Enter content", default="default")
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.input = {}

    with patch("zrb.input.text_input.TextInput.get_default_str") as mock_default:
        mock_default.return_value = "default"
        html = inp.to_html(shared_ctx)
        assert 'name="content"' in html
        assert 'placeholder="Enter content"' in html
        assert "<textarea" in html
        assert "</textarea>" in html
