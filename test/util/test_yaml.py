from zrb.util.yaml import edit_obj, yaml_dump


def test_yaml_dump_basic():
    obj = {"name": "test", "value": 123}
    expected = "name: test\nvalue: 123\n"
    assert yaml_dump(obj) == expected


def test_yaml_dump_with_key_simple():
    obj = {"user": {"name": "Alice", "age": 30}}
    expected = "name: Alice\nage: 30\n"
    assert yaml_dump(obj, key="user") == expected


def test_yaml_dump_with_key_nested():
    obj = {"data": {"items": [{"id": 1, "name": "Item1"}, {"id": 2, "name": "Item2"}]}}
    expected = "- id: 1\n  name: Item1\n- id: 2\n  name: Item2\n"
    assert yaml_dump(obj, key="data.items") == expected


def test_yaml_dump_with_key_not_found():
    obj = {"user": {"name": "Alice"}}
    expected = "null\n"
    assert yaml_dump(obj, key="user.email") == expected


def test_yaml_dump_with_key_list_index():
    obj = {"items": ["apple", "banana", "cherry"]}
    expected = "banana\n"
    assert yaml_dump(obj, key="items.1") == expected


def test_yaml_dump_with_key_list_index_out_of_bounds():
    obj = {"items": ["apple", "banana"]}
    expected = "null\n"
    assert yaml_dump(obj, key="items.2") == expected


def test_yaml_dump_multiline_string():
    obj = {"message": "Hello,\nthis is a multiline\nstring."}
    expected = "message: |-\n  Hello,\n  this is a multiline\n  string.\n"
    assert yaml_dump(obj) == expected


def test_yaml_dump_none_value():
    obj = {"key1": "value1", "key2": None}
    expected = "key1: value1\nkey2: null\n"
    assert yaml_dump(obj) == expected


def test_edit_obj_simple():
    obj = {"a": {"b": 1}}
    result = edit_obj(obj, "a.b", "2")
    assert result == {"a": {"b": 2}}


def test_edit_obj_create_nested():
    obj = {}
    result = edit_obj(obj, "a.b.c", "hello")
    assert result == {"a": {"b": {"c": "hello"}}}


def test_edit_obj_list_index():
    obj = {"items": ["one", "two", "three"]}
    result = edit_obj(obj, "items.1", "new_two")
    assert result == {"items": ["one", "new_two", "three"]}


def test_edit_obj_parse_value():
    obj = {"flag": False}
    result = edit_obj(obj, "flag", "true")
    assert result == {"flag": True}
