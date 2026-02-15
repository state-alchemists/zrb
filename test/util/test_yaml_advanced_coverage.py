import pytest

from zrb.util.yaml import edit_obj, yaml_dump


def test_yaml_dump_none():
    assert yaml_dump(None) == "null\n"


def test_yaml_dump_multiline():
    content = "line1\nline2"
    dumped = yaml_dump(content)
    assert "|" in dumped
    assert "line1" in dumped
    assert "line2" in dumped


def test_edit_obj_edge_cases():
    obj = {"a": {"b": 1}}
    # Test updating existing nested key with string value
    new_obj = edit_obj(obj, "a.b", "2")
    assert new_obj["a"]["b"] == 2

    # Test creating new deep nested key
    new_obj = edit_obj(obj, "x.y.z", "3")
    assert new_obj["x"]["y"]["z"] == 3

    # Test with list index
    obj_with_list = {"a": [10, 20]}
    new_obj = edit_obj(obj_with_list, "a.0", "100")
    assert new_obj["a"][0] == 100


def test_edit_obj_parse_value():
    obj = {}
    assert edit_obj(obj, "a", "true")["a"] is True
    assert edit_obj(obj, "a", "false")["a"] is False
    assert edit_obj(obj, "a", "123")["a"] == 123
    assert edit_obj(obj, "a", "1.23")["a"] == 1.23
    assert edit_obj(obj, "a", "null")["a"] is None
