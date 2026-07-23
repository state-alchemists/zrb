import asyncio

import pytest

from zrb.util.run import gather_isolated, run_async


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


@pytest.mark.asyncio
async def test_gather_isolated_returns_all_results_in_order():
    async def value(x):
        await asyncio.sleep(0)
        return x

    assert await gather_isolated(value(1), value(2), value(3)) == [1, 2, 3]


@pytest.mark.asyncio
async def test_gather_isolated_reraises_first_exception():
    async def boom():
        raise ValueError("boom")

    async def ok():
        return "ok"

    with pytest.raises(ValueError, match="boom"):
        await gather_isolated(boom(), ok())


@pytest.mark.asyncio
async def test_gather_isolated_lets_every_sibling_finish_before_raising():
    # The whole point of the helper: a failing sibling must not orphan the
    # others. Plain asyncio.gather would propagate on first exception, leaving
    # the slow sibling still running.
    finished = []

    async def slow_ok():
        await asyncio.sleep(0.02)
        finished.append("slow")
        return "slow"

    async def fast_fail():
        await asyncio.sleep(0.01)
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        await gather_isolated(slow_ok(), fast_fail())
    # slow_ok ran to completion before the exception surfaced
    assert finished == ["slow"]
