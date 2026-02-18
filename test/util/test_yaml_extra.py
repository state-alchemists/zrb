import pytest

from zrb.util.yaml import _sanitize_obj, edit_obj, yaml_dump


def test_edit_obj_empty_key_scalar():
    assert edit_obj({"a": 1}, "", "2") == 2


def test_edit_obj_empty_key_dict_merge():
    assert edit_obj({"a": 1}, "", "b: 2") == {"a": 1, "b": 2}


def test_sanitize_obj_complex():
    class Complex:
        pass

    obj = {"a": 1, "b": Complex()}
    sanitized = _sanitize_obj(obj)
    assert sanitized == {"a": 1}


def test_sanitize_obj_tuple_and_set():
    obj = {"t": (1, 2), "s": {1, 2}}
    sanitized = _sanitize_obj(obj)
    assert sanitized["t"] == [1, 2]
    assert sanitized["s"] == [1, 2]


def test_edit_obj_list_errors():
    obj = [1, 2]
    with pytest.raises(IndexError):
        edit_obj(obj, "5", "10")
    with pytest.raises(KeyError):
        edit_obj(obj, "not_an_int", "10")


def test_edit_obj_replace_other_type():
    # If obj is string, setting a key converts it to a dict?
    # No, _set_obj_value says:
    # else: # Handle other types by converting to dict
    assert edit_obj("not_a_dict", "key", "val") == {"key": "val"}
    assert edit_obj("not_a_dict", "a.b", "val") == {"a": {"b": "val"}}


def test_yaml_dump_nested_key():
    obj = {"a": {"b": 1, "c": 2}}
    assert yaml_dump(obj, "a.b") == "1\n"
