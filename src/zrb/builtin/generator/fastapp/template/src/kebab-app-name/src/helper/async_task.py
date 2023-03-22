from typing import Awaitable, Callable
import asyncio
import inspect


def create_task(
    awaitable: Awaitable,
    on_error: Callable
) -> asyncio.Task:
    async def critical_task(awaitable):
        try:
            return await awaitable
        except Exception as exception:
            if inspect.iscoroutinefunction(on_error):
                return await on_error(exception)
            return on_error(exception)
    return asyncio.create_task(critical_task(awaitable))
