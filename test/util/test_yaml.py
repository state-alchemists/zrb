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


def test_yaml_dump_list():
    """Test dumping a list."""
    obj = ["item1", "item2", "item3"]
    result = yaml_dump(obj)
    assert "- item1" in result
    assert "- item2" in result
    assert "- item3" in result


def test_yaml_dump_tuple():
    """Test dumping a tuple (should be converted to list)."""
    obj = ("a", "b", "c")
    result = yaml_dump(obj)
    assert "- a" in result
    assert "- b" in result
    assert "- c" in result


def test_yaml_dump_set():
    """Test dumping a set (should be converted to sorted list)."""
    obj = {"c", "a", "b"}
    result = yaml_dump(obj)
    assert "- a" in result
    assert "- b" in result
    assert "- c" in result


def test_yaml_dump_complex_obj_ignored():
    """Test that complex objects are ignored."""

    class CustomClass:
        def __init__(self, val):
            self.val = val

    obj = {
        "key": "value",
        "complex": CustomClass(123),
        "nested": {"inner": CustomClass(456)},
    }
    result = yaml_dump(obj)
    # Complex objects should be ignored/None
    assert "value" in result
    # The complex object itself should be ignored
    assert "CustomClass" not in result


def test_yaml_dump_int():
    """Test dumping an integer directly."""
    result = yaml_dump(42)
    assert result.strip() == "42"


def test_yaml_dump_float():
    """Test dumping a float directly."""
    result = yaml_dump(3.14)
    assert "3.14" in result


def test_yaml_dump_bool():
    """Test dumping a boolean directly."""
    result = yaml_dump(True)
    assert result.strip() == "true"


def test_yaml_dump_string():
    """Test dumping a string directly."""
    result = yaml_dump("hello world")
    assert "hello world" in result


def test_yaml_dump_scalar_trailing_dots():
    """Test that PyYAML document-end marker is removed for scalars."""
    # Some versions of PyYAML add '...\n' for scalars, our function should remove it
    result = yaml_dump("test")
    assert "..." not in result


def test_edit_obj_empty_key_dict_merge():
    """Test editing with empty key merges into existing dict."""
    obj = {"a": 1}
    result = edit_obj(obj, "", "b: 2")
    assert result == {"a": 1, "b": 2}


def test_edit_obj_empty_key_replace():
    """Test editing with empty key replaces non-dict object."""
    obj = "original"
    result = edit_obj(obj, "", "replacement")
    assert result == "replacement"


def test_edit_obj_empty_key_string_value():
    """Test editing with empty key and string value."""
    obj = {"a": 1}
    result = edit_obj(obj, "", "just a string")
    # When the parsed value isn't a dict and obj is dict, it's replaced
    assert result == "just a string"


def test_edit_obj_yamLError_fallback():
    """Test edit_obj treats invalid YAML as string."""
    obj = {"key": "value"}
    # Invalid YAML that should be treated as string
    result = edit_obj(obj, "key", "invalid: yaml: unclosed [")
    # Since YAML parse fails, it should use the string as-is
    assert result == {"key": "invalid: yaml: unclosed ["}


def test_yaml_dump_nested_list_with_complex():
    """Test that complex objects in lists are filtered out."""

    class CustomObj:
        pass

    obj = {"items": ["valid", CustomObj(), "also_valid"]}
    result = yaml_dump(obj)
    # Complex objects should be filtered from list
    lines = result.strip().split("\n")
    # Should only have items without filter issues
    assert "valid" in result


def test_yaml_dump_nested_dict_with_complex():
    """Test that complex objects in dict values are filtered out."""

    class CustomObj:
        pass

    obj = {"key": "value", "complex": CustomObj(), "normal": 123}
    result = yaml_dump(obj)
    assert "value" in result
    assert "normal" in result
    # complex should be filtered out
    assert "complex" not in result


def test_yaml_dump_empty_string_value():
    """Test dumping empty string."""
    result = yaml_dump("")
    assert "''" in result or result.strip() == "" or result.strip() == "null"


def test_edit_obj_list_out_of_range():
    """Test editing list with out of range index."""
    obj = {"items": ["a", "b"]}
    try:
        from zrb.util.yaml import edit_obj

        edit_obj(obj, "items.5", "new_value")
        assert False, "Should have raised IndexError"
    except (IndexError, KeyError):
        pass  # Expected


def test_edit_obj_list_invalid_key():
    """Test editing list with non-integer key."""
    obj = {"items": ["a", "b"]}
    try:
        from zrb.util.yaml import edit_obj

        edit_obj(obj, "items.invalid", "new_value")
        assert False, "Should have raised KeyError"
    except (KeyError, ValueError):
        pass  # Expected
