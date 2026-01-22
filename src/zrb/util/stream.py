import asyncio
import inspect
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def to_infinite_stream(
    func: Callable[[], T | Awaitable[T]],
) -> Callable[[], AsyncIterable[T]]:
    """
    Convert a synchronous or asynchronous function into a function that returns an infinite
    AsyncIterable.
    The AsyncIterable will repeatedly yield the result of the function.

    Args:
        func: A callable (synchronous or asynchronous) that returns a value.

    Returns:
        A callable that returns an infinite AsyncIterable yielding values from func.
    """

    async def stream() -> AsyncIterable[T]:
        while True:
            await asyncio.sleep(0)
            result = func()
            if inspect.isawaitable(result):
                yield await result
            else:
                yield result

    return stream
