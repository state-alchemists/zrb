import asyncio

import pytest

from zrb.util.run import run_async


@pytest.mark.asyncio
async def test_run_async_with_non_awaitable():
    assert await run_async(42) == 42


@pytest.mark.asyncio
async def test_run_async_with_coroutine():
    async def coro():
        return 42

    assert await run_async(coro()) == 42


@pytest.mark.asyncio
async def test_run_async_with_task():
    async def coro():
        return 42

    task = asyncio.create_task(coro())
    assert await run_async(task) == 42
