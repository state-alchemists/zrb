import pytest

from zrb.attr.tpl import Tpl
from zrb.util.attr import (
    get_attr,
    get_bool_attr,
    get_float_attr,
    get_int_attr,
    get_str_attr,
    get_str_dict_attr,
    get_str_list_attr,
)


class MockContext:
    def __init__(self):
        self.render_fn = lambda x: f"rendered_{x}"

    def render(self, x):
        return self.render_fn(x)


@pytest.fixture
def mock_ctx():
    return MockContext()


def test_get_attr(mock_ctx):
    # None attr, constant default
    assert get_attr(mock_ctx, None, "default") == "default"
    # None attr, callable default
    assert get_attr(mock_ctx, None, lambda c: "callable_default") == "callable_default"
    # Callable attr
    assert get_attr(mock_ctx, lambda c: "callable_attr", "default") == "callable_attr"
    # A bare string is a literal — never rendered
    assert get_attr(mock_ctx, "val", "default") == "val"
    # A Tpl opts into rendering
    assert get_attr(mock_ctx, Tpl("val"), "default") == "rendered_val"


def test_get_str_attr(mock_ctx):
    assert get_str_attr(mock_ctx, "val") == "val"
    assert get_str_attr(mock_ctx, Tpl("val")) == "rendered_val"
    assert get_str_attr(mock_ctx, None, default="def") == "def"
    assert get_str_attr(mock_ctx, 123) == "123"
    assert get_str_attr(mock_ctx, None, default=None) == ""


def test_get_bool_attr(mock_ctx):
    mock_ctx.render_fn = lambda x: x  # identity, so Tpl round-trips its text
    assert get_bool_attr(mock_ctx, True) is True
    assert get_bool_attr(mock_ctx, Tpl("true")) is True
    assert get_bool_attr(mock_ctx, "true") is True
    assert get_bool_attr(mock_ctx, "false") is False
    assert get_bool_attr(mock_ctx, None, default=True) is True
    assert get_bool_attr(mock_ctx, None) is False


def test_get_int_attr(mock_ctx):
    mock_ctx.render_fn = lambda x: x
    assert get_int_attr(mock_ctx, 123) == 123
    assert get_int_attr(mock_ctx, Tpl("456")) == 456
    assert get_int_attr(mock_ctx, "456") == 456
    assert get_int_attr(mock_ctx, None, default=789) == 789
    assert get_int_attr(mock_ctx, None) == 0


def test_get_float_attr(mock_ctx):
    mock_ctx.render_fn = lambda x: x
    assert get_float_attr(mock_ctx, 12.3) == 12.3
    assert get_float_attr(mock_ctx, Tpl("45.6")) == 45.6
    assert get_float_attr(mock_ctx, "45.6") == 45.6
    assert get_float_attr(mock_ctx, None, default=7.8) == 7.8
    assert get_float_attr(mock_ctx, None) == 0.0


def test_get_str_list_attr(mock_ctx):
    mock_ctx.render_fn = lambda x: f"r_{x}"
    assert get_str_list_attr(mock_ctx, ["a", "b"]) == ["a", "b"]
    assert get_str_list_attr(mock_ctx, [Tpl("a"), "b"]) == ["r_a", "b"]
    assert get_str_list_attr(mock_ctx, lambda c: ["c"]) == ["c"]
    assert get_str_list_attr(mock_ctx, None) == []


def test_get_str_dict_attr(mock_ctx):
    mock_ctx.render_fn = lambda x: f"r_{x}"
    assert get_str_dict_attr(mock_ctx, {"k": "v"}) == {"k": "v"}
    assert get_str_dict_attr(mock_ctx, {"k": Tpl("v")}) == {"k": "r_v"}
    assert get_str_dict_attr(mock_ctx, lambda c: {"k2": "v2"}) == {"k2": "v2"}
    assert get_str_dict_attr(mock_ctx, None) == {}
