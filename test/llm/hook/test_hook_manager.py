import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import (
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
)
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator


@pytest.fixture
def manager():
    return HookManager(auto_load=False)


@pytest.mark.asyncio
async def test_hook_priority(manager):
    async def low_priority_hook(ctx):
        return HookResult(success=True, output="low")

    async def high_priority_hook(ctx):
        return HookResult(success=True, output="high")

    manager.register(
        low_priority_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="low",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=10,
        ),
    )
    manager.register(
        high_priority_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="high",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=100,
        ),
    )

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert len(results) == 2
    assert results[0].message == "high"
    assert results[1].message == "low"


@pytest.mark.asyncio
async def test_hook_blocking_exit_code_2(manager):
    executed = []

    async def blocking_hook(ctx):
        executed.append("blocking")
        return HookResult.block("Blocked by hook")

    async def subsequent_hook(ctx):
        executed.append("subsequent")
        return HookResult(success=True)

    manager.register(
        blocking_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="blocking",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=100,
        ),
    )
    manager.register(
        subsequent_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="subsequent",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=10,
        ),
    )

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert "blocking" in executed
    assert len(results) == 1
    assert results[0].exit_code == 2


@pytest.mark.asyncio
async def test_hook_continue_false(manager):
    executed = []

    async def stop_hook(ctx):
        executed.append("stop")
        return HookResult(success=True, modifications={"continue": False})

    async def subsequent_hook(ctx):
        executed.append("subsequent")
        return HookResult(success=True)

    manager.register(
        stop_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="stop",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=100,
        ),
    )
    manager.register(
        subsequent_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="subsequent",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=10,
        ),
    )

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert "stop" in executed
    assert len(results) == 1
    assert results[0].continue_execution is False


@pytest.mark.asyncio
async def test_execute_hooks_simple(manager):
    async def my_hook(ctx):
        return HookResult(success=True, output="Hello")

    manager.register(my_hook, events=[HookEvent.SESSION_START])

    results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})
    assert len(results) == 1
    assert results[0].success
    assert results[0].output == "Hello"


def test_scan_and_load_from_path(manager, tmp_path):
    # Create a dummy hook file
    hook_dir = tmp_path / "hooks"
    hook_dir.mkdir()
    hook_file = hook_dir / "test.json"
    hook_content = [
        {
            "name": "test-hook",
            "events": ["SessionStart"],
            "type": "command",
            "config": {"command": "echo hello"},
        }
    ]
    with open(hook_file, "w") as f:
        json.dump(hook_content, f)

    manager.scan(search_dirs=[str(hook_dir)])

    assert HookEvent.SESSION_START in manager._hooks
    assert len(manager._hooks[HookEvent.SESSION_START]) == 1


@pytest.mark.asyncio
async def test_execute_hooks_exception(manager):
    async def failing_hook(ctx):
        raise ValueError("Hook failed")

    manager.register(failing_hook, events=[HookEvent.SESSION_START])
    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert len(results) == 1
    assert results[0].success is False
    assert "Hook failed" in results[0].message
