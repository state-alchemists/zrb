import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.callable", attrs=["dark"]))


@typechecked
async def run_async(fn: Callable, *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    coro = asyncio.to_thread(fn, *args, **kwargs)
    task = asyncio.create_task(coro)
    return await task
