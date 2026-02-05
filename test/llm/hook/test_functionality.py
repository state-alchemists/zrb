import json
import os

import pytest

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent, HookType


@pytest.mark.asyncio
async def test_python_hook_execution():
    manager = HookManager(auto_load=False)
    executed = []

    async def my_hook(context: HookContext) -> HookResult:
        executed.append(context)
        return HookResult(success=True)

    manager.register(my_hook, events=[HookEvent.SESSION_START])

    await manager.execute_hooks(HookEvent.SESSION_START, {"test": "data"})

    assert len(executed) == 1
    assert executed[0].event == HookEvent.SESSION_START
    assert executed[0].event_data == {"test": "data"}


@pytest.mark.asyncio
async def test_config_file_loading_and_hydration(tmp_path):
    # Create a dummy hook config file
    hook_config = {
        "name": "test-file-hook",
        "description": "A test hook from file",
        "events": ["SessionStart"],
        "type": "command",
        "config": {"command": "echo 'Hello from file'", "shell": True},
    }

    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    with open(hooks_dir / "my_hook.json", "w") as f:
        json.dump(hook_config, f)

    # Initialize manager pointing to this dir
    manager = HookManager(auto_load=True, scan_dirs=[hooks_dir])

    # Execute hooks
    results = await manager.execute_hooks(HookEvent.SESSION_START, {})

    # We implemented real hydration for CommandHook
    assert len(results) >= 1
    found = False
    for res in results:
        if res.output and "Hello from file" in res.output:
            found = True
            break
    assert found


@pytest.mark.asyncio
async def test_pre_tool_use_modification():
    manager = HookManager(auto_load=False)

    async def modifier_hook(context: HookContext) -> HookResult:
        if context.event_data.get("tool") == "my_tool":
            return HookResult(
                success=True, modifications={"tool_args": {"extra_arg": "injected"}}
            )
        return HookResult(success=True)

    manager.register(modifier_hook, events=[HookEvent.PRE_TOOL_USE])

    results = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, {"tool": "my_tool", "args": {"original": "value"}}
    )

    assert len(results) == 1
    assert results[0].modifications["tool_args"] == {"extra_arg": "injected"}
