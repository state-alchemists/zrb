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


def test_xcom_repr():
    xcom = Xcom(["a", "b"])
    assert repr(xcom) == "<Xcom ['a', 'b']>"


def test_xcom_popright():
    xcom = Xcom(["a", "b"])
    assert xcom.popright() == "b"
    assert list(xcom) == ["a"]


def test_xcom_get():
    xcom = Xcom(["a"])
    assert xcom.get() == "a"
    assert xcom.get("default") == "a"
    xcom.pop()
    assert xcom.get() is None
    assert xcom.get("default") == "default"


def test_xcom_set():
    xcom = Xcom(["a", "b"])
    xcom.set("c")
    assert list(xcom) == ["c"]


def test_xcom_callbacks():
    push_count = 0
    pop_count = 0

    def on_push():
        nonlocal push_count
        push_count += 1

    def on_pop():
        nonlocal pop_count
        pop_count += 1

    xcom = Xcom()
    xcom.add_push_callback(on_push)
    xcom.add_pop_callback(on_pop)

    xcom.push("a")
    assert push_count == 1
    xcom.append("b")
    assert push_count == 2

    xcom.pop()
    assert pop_count == 1
    xcom.popleft()
    assert pop_count == 2
    xcom.push("c")
    xcom.popright()
    assert pop_count == 3
