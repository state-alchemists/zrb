import functools

from zrb.util.callable import get_callable_name


def test_get_callable_name_function():
    def my_func():
        pass

    assert get_callable_name(my_func) == "my_func"


def test_get_callable_name_partial():
    def my_func(a):
        pass

    p = functools.partial(my_func, a=1)
    assert get_callable_name(p) == "my_func"


def test_get_callable_name_method():
    class A:
        def my_method(self):
            pass

    a = A()
    assert get_callable_name(a.my_method) == "my_method"


def test_get_callable_name_callable_instance():
    class CallableClass:
        def __call__(self):
            pass

    c = CallableClass()
    assert get_callable_name(c) == "CallableClass"


def test_get_callable_name_lambda():
    l = lambda: None
    assert get_callable_name(l) == "<lambda>"


def test_get_callable_name_wrapped():
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    @decorator
    def wrapped_func():
        pass

    # inspect.unwrap should find the original function name
    assert get_callable_name(wrapped_func) == "wrapped_func"
