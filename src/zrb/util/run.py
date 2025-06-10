import asyncio
import inspect
from typing import Any


async def run_async(value: Any) -> Any:
    """
    Run a value asynchronously, awaiting if it's awaitable or running in a thread if not.

    Args:
        value (Any): The value to run. Can be awaitable or not.

    Returns:
        Any: The result of the awaited value or the value itself if not awaitable.
    """
    if isinstance(value, asyncio.Task):
        return value
    if inspect.isawaitable(value):
        return await value
    return await asyncio.to_thread(lambda: value)
