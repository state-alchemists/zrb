import asyncio
import inspect
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def to_infinite_stream(
    func: Callable[[], T | Awaitable[T]],
) -> Callable[[], AsyncIterable[T]]:
    """Wraps `func` (sync or async) as a callable returning an infinite
    `AsyncIterable` that repeatedly yields its result."""

    async def stream() -> AsyncIterable[T]:
        while True:
            await asyncio.sleep(0)
            result = func()
            if inspect.isawaitable(result):
                yield await result
            else:
                yield result

    return stream
