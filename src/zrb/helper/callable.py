from typing import Any, Callable
import inspect


async def run_async(
    fn: Callable, *args: Any, **kwargs: Any
) -> Any:
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)
