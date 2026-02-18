from types import MethodType

from zrb.util.callable import get_callable_name


def test_get_callable_name_bound_method():
    class A:
        def my_method(self):
            pass

    a = A()
    assert get_callable_name(a.my_method) == "my_method"


def test_get_callable_name_fallback():
    # Something that is not a function, not a partial, has no __name__, not MethodType, not callable
    class NoName:
        pass

    obj = NoName()
    # Remove __call__ if it exists (it doesn't here)
    assert get_callable_name(obj) == repr(obj)


def test_get_callable_name_instance():
    class CallableObj:
        def __call__(self):
            pass

    obj = CallableObj()
    assert get_callable_name(obj) == "CallableObj"
