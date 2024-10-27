from typing import Any

import asyncio
import inspect


async def run_async(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return await asyncio.to_thread(lambda: value)
