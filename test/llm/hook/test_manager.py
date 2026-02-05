import pytest

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_hook_manager_execution():
    manager = HookManager()

    executed = []

    async def my_hook(context: HookContext) -> HookResult:
        executed.append(context)
        return HookResult(success=True)

    manager.register(my_hook, events=[HookEvent.SESSION_START])

    results = await manager.execute_hooks(HookEvent.SESSION_START, {"foo": "bar"})

    assert len(executed) == 1
    assert executed[0].event == HookEvent.SESSION_START
    assert executed[0].event_data == {"foo": "bar"}
    assert len(results) == 1
    assert results[0].success


@pytest.mark.asyncio
async def test_global_hook_execution():
    manager = HookManager()

    executed = []

    async def my_hook(context: HookContext) -> HookResult:
        executed.append(context)
        return HookResult(success=True)

    # Register as global hook
    manager.register(my_hook)

    await manager.execute_hooks(HookEvent.SESSION_START, {})
    await manager.execute_hooks(HookEvent.STOP, {})

    assert len(executed) == 2
