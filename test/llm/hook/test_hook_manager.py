"""Tests for HookManager class using Public API."""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.types import HookEvent, HookType

@pytest.fixture
def manager():
    return HookManager()

class TestHookManagerBehavior:
    """Test behavior via public register and execute_hooks methods."""

    @pytest.mark.asyncio
    async def test_hook_priority_sorting(self, manager):
        # Hooks should execute based on priority, regardless of registration order
        async def h1(ctx): return HookResult(success=True, output="P10")
        async def h2(ctx): return HookResult(success=True, output="P100")

        manager.register(h1, config=HookConfig(
            name="low", events=[], type=HookType.COMMAND,
            config=CommandHookConfig(command=""), priority=10,
        ))
        manager.register(h2, config=HookConfig(
            name="high", events=[], type=HookType.COMMAND,
            config=CommandHookConfig(command=""), priority=100,
        ))

        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert results[0].message == "P100"
        assert results[1].message == "P10"

    @pytest.mark.asyncio
    async def test_blocking_hook_stops_execution(self, manager):
        executed = []
        async def blocking_hook(ctx):
            executed.append("blocking")
            return HookResult.block("Blocked by hook")
        async def subsequent_hook(ctx):
            executed.append("subsequent")
            return HookResult(success=True)

        manager.register(blocking_hook, events=[HookEvent.SESSION_START])
        manager.register(subsequent_hook, events=[HookEvent.SESSION_START])

        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert "blocking" in executed
        assert "subsequent" not in executed
        assert results[0].exit_code == 2

    @pytest.mark.asyncio
    async def test_continue_false_stops_execution(self, manager):
        executed = []
        async def stop_hook(ctx):
            executed.append("stop")
            return HookResult(success=True, modifications={"continue": False})
        async def subsequent_hook(ctx):
            executed.append("subsequent")
            return HookResult(success=True)

        manager.register(stop_hook, events=[HookEvent.SESSION_START])
        manager.register(subsequent_hook, events=[HookEvent.SESSION_START])

        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert "stop" in executed
        assert "subsequent" not in executed
        assert results[0].continue_execution is False

    @pytest.mark.asyncio
    async def test_hook_manager_handles_hook_exceptions(self, manager):
        async def failing_hook(ctx):
            raise ValueError("Intentional Failure")
        
        manager.register(failing_hook, events=[HookEvent.SESSION_START])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1
        assert results[0].success is False
        assert "Intentional Failure" in results[0].message

    @pytest.mark.asyncio
    async def test_scan_loads_from_json(self, manager, tmp_path):
        hook_dir = tmp_path / "hooks"
        hook_dir.mkdir()
        hook_file = hook_dir / "test.json"
        with open(hook_file, "w") as f:
            json.dump([{"name": "test-hook", "events": ["SessionStart"], "type": "command", "config": {"command": "echo hello"}}], f)

        manager.scan(search_dirs=[str(hook_dir)])
        # Use simple execution to verify the hook was loaded and registered
        results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_global_hooks_run_for_any_event(self, manager):
        executed = []
        async def global_hook(ctx):
            executed.append(ctx.event)
            return HookResult(success=True)

        manager.register(global_hook) # No events = global
        
        await manager.execute_hooks(HookEvent.SESSION_START, {})
        await manager.execute_hooks(HookEvent.NOTIFICATION, {})
        assert HookEvent.SESSION_START in executed
        assert HookEvent.NOTIFICATION in executed
