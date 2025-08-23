from zrb.util.truncate import truncate_str


def test_truncate_str_string():
    assert truncate_str("hello world", 15) == "hello world"
    assert truncate_str("hello world", 11) == "hello world"
    assert truncate_str("hello world", 10) == "hello  ..."
    assert truncate_str("hello world", 5) == "h ..."
    assert truncate_str("hello world", 3) == "hel"
    assert truncate_str("short", 10) == "short"


def test_truncate_str_dict():
    data = {"a": "hello world", "b": "another long string"}
    truncated = truncate_str(data, 10)
    assert truncated["a"] == "hello  ..."
    assert truncated["b"] == "anothe ..."


def test_truncate_str_list():
    data = ["hello world", "another long string"]
    truncated = truncate_str(data, 10)
    assert truncated[0] == "hello  ..."
    assert truncated[1] == "anothe ..."


def test_truncate_str_tuple():
    data = ("hello world", "another long string")
    truncated = truncate_str(data, 10)
    assert isinstance(truncated, tuple)
    assert truncated[0] == "hello  ..."
    assert truncated[1] == "anothe ..."


def test_truncate_str_set():
    data = {"hello world", "another long string"}
    truncated = truncate_str(data, 10)
    assert isinstance(truncated, set)
    assert "hello  ..." in truncated
    assert "anothe ..." in truncated


def test_truncate_str_nested():
    data = {
        "a": ["hello world", ("short", "another very long string")],
        "b": {"c": "a third long string here"},
    }
    truncated = truncate_str(data, 12)
    assert truncated["a"][0] == "hello world"
    assert truncated["a"][1][0] == "short"
    assert truncated["a"][1][1] == "another  ..."
    assert truncated["b"]["c"] == "a third  ..."


def test_truncate_str_other_types():
    assert truncate_str(123, 10) == 123
    assert truncate_str(123.45, 10) == 123.45
    assert truncate_str(True, 10) is True
    assert truncate_str(None, 10) is None
    assert truncate_str(b"byte string", 10) == b"byte string"
