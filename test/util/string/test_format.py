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

def test_fstring_format_blocks_class_hierarchy_traversal():
    """The builtins whitelist alone cannot stop this — dunders must be rejected.

    ``().__class__.__bases__[0].__subclasses__()`` walks from any object to
    ``object`` and enumerates every loaded class, which is the first step of the
    standard eval-sandbox escape.
    """
    template = "{len(().__class__.__bases__[0].__subclasses__())}"
    with pytest.raises(ValueError, match="dunder name"):
        fstring_format(template, {})


def test_fstring_format_blocks_builtins_recovery():
    """Reaching a real module's __globals__ would restore unrestricted eval."""
    template = (
        "{[c for c in ().__class__.__bases__[0].__subclasses__() "
        "if c.__name__ == '_ModuleLock'][0].__init__.__globals__"
        "['__builtins__']['__import__']('os').getpid()}"
    )
    with pytest.raises(ValueError, match="dunder name"):
        fstring_format(template, {})


def test_fstring_format_blocks_bare_dunder_name():
    with pytest.raises(ValueError, match="dunder name '__import__' is not allowed"):
        fstring_format("{__import__}", {})


def test_fstring_format_allows_single_underscore_attribute():
    """Private-ish attributes are legitimate in templates and cannot escape."""

    class Holder:
        _value = 7

    assert fstring_format("{obj._value}", {"obj": Holder()}) == "7"


def test_fstring_format_allows_safe_builtins_and_calls():
    data = {"items": ["b", "a"]}
    assert fstring_format("{len(items)}/{sorted(items)[0]}", data) == "2/a"
