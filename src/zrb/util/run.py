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
