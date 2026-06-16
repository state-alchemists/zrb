import pytest

from zrb.util.string.conversion import (
    double_quote,
    to_boolean,
    to_camel_case,
    to_human_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


def test_double_quote():
    assert double_quote('hello "world"') == '"hello \\"world\\""'
    assert double_quote("hello world") == '"hello world"'


def test_to_boolean_true():
    for s in ["true", "1", "yes", "y", "active", "on"]:
        assert to_boolean(s) is True


def test_to_boolean_false():
    for s in ["false", "0", "no", "n", "inactive", "off"]:
        assert to_boolean(s) is False


def test_to_boolean_invalid():
    with pytest.raises(Exception, match='Cannot infer boolean value from "invalid"'):
        to_boolean("invalid")


def test_to_camel_case():
    assert to_camel_case("hello world") == "helloWorld"
    assert to_camel_case("hello-world") == "helloWorld"
    assert to_camel_case("hello_world") == "helloWorld"
    assert to_camel_case("HelloWorld") == "helloWorld"
    assert to_camel_case(None) == ""


def test_to_pascal_case():
    assert to_pascal_case("hello world") == "HelloWorld"
    assert to_pascal_case("hello-world") == "HelloWorld"
    assert to_pascal_case("hello_world") == "HelloWorld"
    assert to_pascal_case("helloWorld") == "HelloWorld"
    assert to_pascal_case(None) == ""


def test_to_kebab_case():
    assert to_kebab_case("hello world") == "hello-world"
    assert to_kebab_case("hello-world") == "hello-world"
    assert to_kebab_case("hello_world") == "hello-world"
    assert to_kebab_case("HelloWorld") == "hello-world"
    assert to_kebab_case(None) == ""


def test_to_snake_case():
    assert to_snake_case("hello world") == "hello_world"
    assert to_snake_case("hello-world") == "hello_world"
    assert to_snake_case("hello_world") == "hello_world"
    assert to_snake_case("HelloWorld") == "hello_world"
    assert to_snake_case(None) == ""


def test_to_human_case():
    assert to_human_case("hello world") == "hello world"
    assert to_human_case("hello-world") == "hello world"
    assert to_human_case("hello_world") == "hello world"
    assert to_human_case("HelloWorld") == "hello world"
    assert to_human_case(None) == ""
