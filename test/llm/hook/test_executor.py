import asyncio

import pytest

from zrb.llm.hook.executor import (
    ThreadPoolHookExecutor,
    get_hook_executor,
    shutdown_hook_executor,
)
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_executor_lifecycle():
    executor = ThreadPoolHookExecutor(max_workers=2)
    executor.start()

    async with executor.execution_context() as ctx:
        assert ctx == executor

    executor.shutdown()


@pytest.mark.asyncio
async def test_executor_execute_hook():
    executor = ThreadPoolHookExecutor()
    executor.start()

    async def sample_hook(ctx):
        return HookResult(success=True, output="Done")

    ctx = HookContext(
        event=HookEvent.SESSION_START, event_data={}, hook_event_name="start"
    )
    result = await executor.execute_hook(sample_hook, ctx)

    assert result.success is True
    assert result.message == "Done"
    executor.shutdown()


@pytest.mark.asyncio
async def test_executor_timeout():
    executor = ThreadPoolHookExecutor(default_timeout=1)
    executor.start()

    # Keep the durations small: wait_for trips the timeout, but the hook runs in
    # a non-cancellable worker thread, so shutdown(wait=True) below must join the
    # still-sleeping worker. A 0.3s sleep keeps the test meaningful without the
    # ~2s wall-time a longer sleep would cost.
    async def slow_hook(ctx):
        await asyncio.sleep(0.3)
        return HookResult(success=True)

    ctx = HookContext(
        event=HookEvent.SESSION_START, event_data={}, hook_event_name="start"
    )
    result = await executor.execute_hook(slow_hook, ctx, timeout=0.05)

    assert result.success is False
    assert result.exit_code == 124
    executor.shutdown()


def test_executor_singleton():
    executor = get_hook_executor()
    assert executor is not None
    shutdown_hook_executor()
    # After shutdown, it's None internally
