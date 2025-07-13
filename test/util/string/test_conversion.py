import pytest
from zrb.util.string.conversion import (
    double_quote,
    to_boolean,
    to_camel_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
    to_human_case,
    pluralize,
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


def test_pluralize():
    assert pluralize("foot") == "feet"
    assert pluralize("tooth") == "teeth"
    assert pluralize("child") == "children"
    assert pluralize("person") == "people"
    assert pluralize("man") == "men"
    assert pluralize("woman") == "women"
    assert pluralize("mouse") == "mice"
    assert pluralize("goose") == "geese"
    assert pluralize("ox") == "oxen"
    assert pluralize("cactus") == "cacti"
    assert pluralize("focus") == "foci"
    assert pluralize("fungus") == "fungi"
    assert pluralize("nucleus") == "nuclei"
    assert pluralize("syllabus") == "syllabi"
    assert pluralize("analysis") == "analyses"
    assert pluralize("diagnosis") == "diagnoses"
    assert pluralize("thesis") == "theses"
    assert pluralize("crisis") == "crises"
    assert pluralize("phenomenon") == "phenomena"
    assert pluralize("criterion") == "criteria"
    assert pluralize("cat") == "cats"
    assert pluralize("dog") == "dogs"
    assert pluralize("bus") == "buses"
    assert pluralize("box") == "boxes"
    assert pluralize("buzz") == "buzzes"
    assert pluralize("church") == "churches"
    assert pluralize("bush") == "bushes"
    assert pluralize("wolf") == "wolves"
    assert pluralize("knife") == "knives"
    assert pluralize("baby") == "babies"
    assert pluralize("toy") == "toys"

