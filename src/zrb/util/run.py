import asyncio
import inspect
from typing import Any


async def run_async(value: Any) -> Any:
    """
    Run a value asynchronously, awaiting if it's awaitable or returning it directly.

    Args:
        value (Any): The value to run. Can be awaitable or not.

    Returns:
        Any: The result of the awaited value or the value itself if not awaitable.
    """
    if isinstance(value, asyncio.Task):
        return await value
    if inspect.isawaitable(value):
        return await value
    return value


async def gather_isolated(*coros: Any) -> list[Any]:
    """Gather coros, letting every sibling settle before surfacing an error.

    Plain ``asyncio.gather`` propagates the first exception immediately, leaving
    the other coroutines running orphaned. Here every coroutine runs to
    completion, then the first exception is re-raised — same fail-fast contract
    for callers (cancellation included, matching plain gather), no orphaned
    siblings.
    """
    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return results
