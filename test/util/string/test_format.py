import pytest

from zrb.util.string.format import fstring_format


def test_fstring_format_simple():
    template = "Hello, {name}!"
    data = {"name": "world"}
    assert fstring_format(template, data) == "Hello, world!"


def test_fstring_format_multiple():
    template = "{greeting}, {name}!"
    data = {"greeting": "Hi", "name": "there"}
    assert fstring_format(template, data) == "Hi, there!"


def test_fstring_format_with_expression():
    template = "Result: {x * y}"
    data = {"x": 5, "y": 10}
    assert fstring_format(template, data) == "Result: 50"


def test_fstring_format_escaped_braces():
    template = "This is {{not}} a variable: {x}"
    data = {"x": 123}
    assert fstring_format(template, data) == "This is {not} a variable: 123"


def test_fstring_format_invalid_expression():
    template = "Invalid: {z}"
    data = {"x": 1}
    with pytest.raises(ValueError, match="Error evaluating expression 'z'"):
        fstring_format(template, data)
