import asyncio
import inspect
from typing import Awaitable, Callable


def create_task(awaitable: Awaitable, on_error: Callable) -> asyncio.Task:
    async def critical_task(awaitable):
        try:
            return await awaitable
        except (asyncio.CancelledError, GeneratorExit, Exception) as e:
            if inspect.iscoroutinefunction(on_error):
                return await on_error(e)
            return on_error(e)

    return asyncio.create_task(critical_task(awaitable))
