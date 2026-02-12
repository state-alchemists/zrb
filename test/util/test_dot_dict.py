import pytest

from zrb.dot_dict.dot_dict import DotDict


def test_dot_dict_get_attr():
    d = DotDict({"a": 1, "b": 2})
    assert d.a == 1
    assert d.b == 2


def test_dot_dict_get_attr_error():
    d = DotDict({"a": 1})
    with pytest.raises(AttributeError, match="'DotDict' object has no attribute 'b'"):
        _ = d.b


def test_dot_dict_set_attr():
    d = DotDict()
    d.a = 1
    assert d["a"] == 1
    assert d.a == 1


def test_dot_dict_del_attr():
    d = DotDict({"a": 1})
    del d.a
    assert "a" not in d
    with pytest.raises(AttributeError, match="'DotDict' object has no attribute 'a'"):
        del d.a


def test_dot_dict_copy():
    d = DotDict({"a": 1})
    d2 = d.copy()
    assert isinstance(d2, DotDict)
    assert d2.a == 1
    d2.a = 2
    assert d.a == 1
    assert d2.a == 2
