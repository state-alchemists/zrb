from types import BuiltinMethodType, MethodType


def get_callable_name(obj):
    import functools
    import inspect

    # 1. Unwrap decorated functions
    obj = inspect.unwrap(obj, stop=lambda f: not hasattr(f, "__wrapped__"))
    # 2. functools.partial – delegate to the wrapped function
    if isinstance(obj, functools.partial):
        return get_callable_name(obj.func)
    # 3. Plain functions, built‑ins, methods
    if hasattr(obj, "__name__"):
        return obj.__name__
    # 4. Bound or unbound methods of a class
    if isinstance(obj, (MethodType, BuiltinMethodType)):
        return obj.__func__.__name__
    # 5. Instances of classes defining __call__
    if callable(obj):
        return type(obj).__name__
    # 6. Fallback
    return repr(obj)
