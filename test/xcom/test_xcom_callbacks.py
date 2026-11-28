"""The callbacks fire for every mutation `Xcom` inherits, not only the ones it
overrides (review of the tree, 2026-11-28).

`deque`'s own `__iadd__` and `clear` bypassed the overrides, and a trigger fans
out on the push callback, so `xcom += [...]` or a `clear()` between events could
drop a wake-up with no error at all.
"""

from zrb.xcom.xcom import Xcom


def test_iadd_fires_the_push_callbacks():
    xcom = Xcom([])
    sizes = []
    xcom.append_push_callback(lambda: sizes.append(len(xcom)))
    xcom += ["a", "b"]
    assert sizes == [2]
    assert list(xcom) == ["a", "b"]


def test_clear_fires_the_pop_callbacks():
    xcom = Xcom(["a", "b"])
    fired = []
    xcom.append_pop_callback(lambda: fired.append("pop"))
    xcom.clear()
    assert fired == ["pop"]
    assert list(xcom) == []


def test_clear_of_an_empty_queue_fires_nothing():
    xcom = Xcom([])
    fired = []
    xcom.append_pop_callback(lambda: fired.append("pop"))
    xcom.clear()
    assert fired == []


def test_set_fires_one_push_that_sees_only_the_new_value():
    """`set` replaces before it tells anyone. A push listener used to observe
    the old values plus the new one, then watch them disappear one by one."""
    xcom = Xcom(["old", "older"])
    sizes = []
    pops = []
    xcom.append_push_callback(lambda: sizes.append(len(xcom)))
    xcom.append_pop_callback(lambda: pops.append("pop"))
    xcom.set("new")
    assert list(xcom) == ["new"]
    assert sizes == [1]
    assert pops == []
