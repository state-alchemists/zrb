import asyncio

import pytest

from zrb.util.run import run_async


@pytest.mark.asyncio
async def test_run_async_with_direct_value():
    assert await run_async(123) == 123
    assert await run_async("hello") == "hello"
    assert await run_async(None) is None


@pytest.mark.asyncio
async def test_run_async_with_coroutine():
    async def sample_coro():
        return "result"

    assert await run_async(sample_coro()) == "result"


@pytest.mark.asyncio
async def test_run_async_with_task():
    async def sample_coro():
        await asyncio.sleep(0.01)
        return "task result"

    task = asyncio.create_task(sample_coro())
    assert await run_async(task) == "task result"


@pytest.mark.asyncio
async def test_run_async_with_awaitable_object():
    class AwaitableObj:
        def __await__(self):
            yield
            return "awaitable result"

    assert await run_async(AwaitableObj()) == "awaitable result"
