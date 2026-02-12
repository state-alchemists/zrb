import asyncio

import pytest

from zrb.util.stream import to_infinite_stream


@pytest.mark.asyncio
async def test_to_infinite_stream_sync():
    counter = 0

    def sync_func():
        nonlocal counter
        counter += 1
        return counter

    stream_factory = to_infinite_stream(sync_func)
    stream = stream_factory()

    results = []
    async for value in stream:
        results.append(value)
        if len(results) >= 3:
            break

    assert results == [1, 2, 3]


@pytest.mark.asyncio
async def test_to_infinite_stream_async():
    counter = 0

    async def async_func():
        nonlocal counter
        await asyncio.sleep(0.01)
        counter += 1
        return counter

    stream_factory = to_infinite_stream(async_func)
    stream = stream_factory()

    results = []
    async for value in stream:
        results.append(value)
        if len(results) >= 3:
            break

    assert results == [1, 2, 3]
