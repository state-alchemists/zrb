"""Tests for BoolInput class."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_shared_context import AnySharedContext
from zrb.input.bool_input import BoolInput


def test_bool_input_init():
    """Test BoolInput initialization."""
    inp = BoolInput(
        name="enable_feature",
        description="Enable the feature",
        default=True,
    )
    assert inp.name == "enable_feature"
    assert inp.description == "Enable the feature"


def test_bool_input_get_default_str():
    """Test BoolInput.get_default_str returns string representation."""
    inp = BoolInput(name="flag", default=True)
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.input = {}

    with patch("zrb.input.bool_input.get_bool_attr") as mock_get_bool_attr:
        mock_get_bool_attr.return_value = True
        result = inp.get_default_str(shared_ctx)
        assert result == "True"


def test_bool_input_get_default_str_false():
    """Test BoolInput.get_default_str returns 'False' for False value."""
    inp = BoolInput(name="flag", default=False)
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.input = {}

    with patch("zrb.input.bool_input.get_bool_attr") as mock_get_bool_attr:
        mock_get_bool_attr.return_value = False
        result = inp.get_default_str(shared_ctx)
        assert result == "False"


def test_bool_input_parse_str_value():
    """Test BoolInput._parse_str_value converts strings to bool."""
    inp = BoolInput(name="flag")

    assert inp._parse_str_value("true") is True
    assert inp._parse_str_value("True") is True
    assert inp._parse_str_value("TRUE") is True
    assert inp._parse_str_value("1") is True
    assert inp._parse_str_value("yes") is True

    assert inp._parse_str_value("false") is False
    assert inp._parse_str_value("False") is False
    assert inp._parse_str_value("FALSE") is False
    assert inp._parse_str_value("0") is False
    assert inp._parse_str_value("no") is False


def test_bool_input_to_html():
    """Test BoolInput.to_html generates correct HTML."""
    inp = BoolInput(
        name="enabled",
        description="Enable feature",
        default=True,
    )
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.input = {}

    with patch("zrb.input.bool_input.get_bool_attr") as mock_get_bool_attr:
        mock_get_bool_attr.return_value = True
        html = inp.to_html(shared_ctx)
        assert 'name="enabled"' in html
        assert 'placeholder="Enable feature"' in html
        assert 'value="true"' in html
        assert 'value="false"' in html


def test_bool_input_to_html_false_default():
    """Test BoolInput.to_html with False default."""
    inp = BoolInput(name="enabled", default=False)
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.input = {}

    with patch("zrb.input.bool_input.get_bool_attr") as mock_get_bool_attr:
        mock_get_bool_attr.return_value = False
        html = inp.to_html(shared_ctx)
        assert 'value="true"' in html
        assert 'value="false"' in html


def test_bool_input_auto_render_false():
    """Test BoolInput with auto_render=False."""
    inp = BoolInput(name="flag", default=True, auto_render=False)
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.input = {}

    with patch("zrb.input.bool_input.get_bool_attr") as mock_get_bool_attr:
        mock_get_bool_attr.return_value = True
        result = inp.get_default_str(shared_ctx)
        assert result == "True"
        mock_get_bool_attr.assert_called_once()
