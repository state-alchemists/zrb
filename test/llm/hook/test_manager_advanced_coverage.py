import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent, HookType
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.schema import HookConfig, CommandHookConfig

@pytest.mark.asyncio
async def test_hook_manager_execute_hooks_simple():
    manager = HookManager()
    
    executed = []
    async def my_hook(ctx):
        executed.append(ctx)
        return HookResult(success=True)
        
    manager.register(my_hook, events=[HookEvent.SESSION_START])
    
    # execute_hooks_simple is a public method
    results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {"data": "val"})
    assert len(executed) == 1
    assert len(results) == 1

@pytest.mark.asyncio
async def test_hook_manager_register_with_priority():
    manager = HookManager()
    
    order = []
    async def hook1(ctx):
        await asyncio.sleep(0.2) # Make it slower
        order.append(1)
        return HookResult(success=True)
    async def hook2(ctx):
        await asyncio.sleep(0.1) # Make it faster
        order.append(2)
        return HookResult(success=True)
        
    # Parallel execution via gather means order depends on speed, not priority
    # unless we use blocking hooks or check the results list order.
    # HookManager.execute_hooks returns results in priority order.
    
    config1 = HookConfig(name="h1", events=[HookEvent.SESSION_START], type=HookType.COMMAND, config=CommandHookConfig("echo 1"), priority=10)
    config2 = HookConfig(name="h2", events=[HookEvent.SESSION_START], type=HookType.COMMAND, config=CommandHookConfig("echo 2"), priority=5)
    
    manager.register(hook1, config=config1)
    manager.register(hook2, config=config2)
    
    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    # results list should be [result_from_h1, result_from_h2]
    # because hooks_to_run was sorted.
    # order list might be [2, 1] if hook2 finished faster.
    
    # We want to verify that results are sorted by priority
    # Let's use unique messages to identify results
    async def h1(ctx): return HookResult(success=True, output="P10")
    async def h2(ctx): return HookResult(success=True, output="P5")
    
    m2 = HookManager()
    m2.register(h1, config=config1)
    m2.register(h2, config=config2)
    res = await m2.execute_hooks(HookEvent.SESSION_START, {})
    assert res[0].message == "P10"
    assert res[1].message == "P5"

@pytest.mark.asyncio
async def test_hook_manager_global_hooks():
    manager = HookManager()
    
    executed = []
    async def global_hook(ctx):
        executed.append(ctx.event)
        return HookResult(success=True)
        
    manager.register(global_hook) # Global
    
    await manager.execute_hooks(HookEvent.SESSION_START, {})
    await manager.execute_hooks(HookEvent.NOTIFICATION, {})
    
    assert HookEvent.SESSION_START in executed
    assert HookEvent.NOTIFICATION in executed
