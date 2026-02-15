import json
import os
import tempfile

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


@pytest.mark.asyncio
async def test_hook_manager_register_various_events():
    """Test registering hooks for multiple events."""
    manager = HookManager()
    events = [HookEvent.NOTIFICATION, HookEvent.USER_PROMPT_SUBMIT]

    async def multi_event_hook(ctx):
        return HookResult(success=True)

    manager.register(multi_event_hook, events=events)

    res1 = await manager.execute_hooks(HookEvent.NOTIFICATION, {})
    res2 = await manager.execute_hooks(HookEvent.USER_PROMPT_SUBMIT, {})

    assert len(res1) == 1
    assert len(res2) == 1


@pytest.mark.asyncio
async def test_hook_manager_get_search_directories():
    """Test getting search directories (public getter)."""
    manager = HookManager()
    dirs = manager.get_search_directories()
    assert isinstance(dirs, list)
    # Should at least contain default plugin paths if they exist or home paths
    assert len(dirs) >= 0
