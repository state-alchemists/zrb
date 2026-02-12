from unittest.mock import MagicMock

import pytest

from zrb.util.attr import (
    get_attr,
    get_bool_attr,
    get_float_attr,
    get_int_attr,
    get_str_attr,
    get_str_dict_attr,
    get_str_list_attr,
)


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.render.side_effect = lambda x: f"rendered_{x}"
    return ctx


def test_get_attr(mock_ctx):
    # None attr, constant default
    assert get_attr(mock_ctx, None, "default") == "default"
    # None attr, callable default
    assert get_attr(mock_ctx, None, lambda c: "callable_default") == "callable_default"
    # Callable attr
    assert get_attr(mock_ctx, lambda c: "callable_attr", "default") == "callable_attr"
    # String attr with auto_render
    assert get_attr(mock_ctx, "val", "default", auto_render=True) == "rendered_val"
    # String attr without auto_render
    assert get_attr(mock_ctx, "val", "default", auto_render=False) == "val"


def test_get_str_attr(mock_ctx):
    assert get_str_attr(mock_ctx, "val") == "rendered_val"
    assert get_str_attr(mock_ctx, None, default="def") == "def"
    assert get_str_attr(mock_ctx, 123) == "123"
    assert get_str_attr(mock_ctx, None, default=None) == ""


def test_get_bool_attr(mock_ctx):
    mock_ctx.render.side_effect = lambda x: x  # Disable rendering for bool test
    assert get_bool_attr(mock_ctx, True) is True
    assert get_bool_attr(mock_ctx, "true") is True
    assert get_bool_attr(mock_ctx, "false") is False
    assert get_bool_attr(mock_ctx, None, default=True) is True
    assert get_bool_attr(mock_ctx, None) is False


def test_get_int_attr(mock_ctx):
    mock_ctx.render.side_effect = lambda x: x
    assert get_int_attr(mock_ctx, 123) == 123
    assert get_int_attr(mock_ctx, "456") == 456
    assert get_int_attr(mock_ctx, None, default=789) == 789
    assert get_int_attr(mock_ctx, None) == 0


def test_get_float_attr(mock_ctx):
    mock_ctx.render.side_effect = lambda x: x
    assert get_float_attr(mock_ctx, 12.3) == 12.3
    assert get_float_attr(mock_ctx, "45.6") == 45.6
    assert get_float_attr(mock_ctx, None, default=7.8) == 7.8
    assert get_float_attr(mock_ctx, None) == 0.0


def test_get_str_list_attr(mock_ctx):
    mock_ctx.render.side_effect = lambda x: f"r_{x}"
    assert get_str_list_attr(mock_ctx, ["a", "b"]) == ["r_a", "r_b"]
    assert get_str_list_attr(mock_ctx, lambda c: ["c"]) == ["c"]
    assert get_str_list_attr(mock_ctx, None) == []


def test_get_str_dict_attr(mock_ctx):
    mock_ctx.render.side_effect = lambda x: f"r_{x}"
    assert get_str_dict_attr(mock_ctx, {"k": "v"}) == {"k": "r_v"}
    assert get_str_dict_attr(mock_ctx, lambda c: {"k2": "v2"}) == {"k2": "v2"}
    assert get_str_dict_attr(mock_ctx, None) == {}
