"""Run blocking callables without making interpreter shutdown wait for them."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")


async def run_in_daemon(
    func: Callable[..., _T], *args: object, name: str = "zrb-daemon"
) -> _T:
    """Run *func* on a daemon thread and await its result.

    Cancellation stops waiting for the callable but cannot stop code already
    running in the thread. The daemon thread is intentional: a blocking native
    call that outlives its cancelled caller must not hold interpreter shutdown.
    """
    loop = asyncio.get_running_loop()
    result: asyncio.Future[_T] = loop.create_future()

    def settle(setter: Callable[..., None], value: object) -> None:
        if not result.done():
            setter(value)

    def post(setter: Callable[..., None], value: object) -> None:
        try:
            loop.call_soon_threadsafe(settle, setter, value)
        except RuntimeError:
            # The loop closed while the daemon call was still unwinding.
            pass

    def run() -> None:
        try:
            value = func(*args)
        except BaseException as error:
            post(result.set_exception, error)
        else:
            post(result.set_result, value)

    threading.Thread(target=run, name=name, daemon=True).start()
    return await result
