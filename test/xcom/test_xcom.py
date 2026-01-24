import pytest

from zrb.xcom.xcom import Xcom


def test_xcom_push_and_peek():
    xcom = Xcom([])
    xcom.push("data1")
    assert xcom.peek() == "data1"
    xcom.push("data2")
    assert xcom.peek() == "data1"  # FIFO behavior, peek returns the oldest


def test_xcom_peek_empty():
    xcom = Xcom([])
    with pytest.raises(IndexError):
        xcom.peek()


def test_xcom_pop():
    xcom = Xcom([])
    xcom.push("data1")
    xcom.push("data2")
    assert xcom.pop() == "data1"  # FIFO behavior, pop removes the oldest
    assert xcom.peek() == "data2"


def test_xcom_pop_empty():
    xcom = Xcom([])
    with pytest.raises(IndexError):
        xcom.pop()


def test_xcom_len():
    xcom = Xcom([])
    assert len(xcom) == 0
    xcom.push("data1")
    assert len(xcom) == 1


def test_xcom_iter():
    xcom = Xcom(["a", "b"])
    results = [item for item in xcom]
    assert results == ["a", "b"]


def test_xcom_getitem():
    xcom = Xcom(["a", "b"])
    assert xcom[0] == "a"
    assert xcom[1] == "b"
