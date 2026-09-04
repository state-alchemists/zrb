"""Tests for HookManager class using Public API."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.executor import HookExecutionResult
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.types import HookEvent, HookType


@pytest.fixture
def manager():
    """Create HookManager for tests."""
    mock_cfg = MagicMock()
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.HOOKS_DIRS = []
    with patch("zrb.llm.hook.manager.CFG", mock_cfg):
        yield HookManager(search_dirs=[])


class TestHookManagerLifecycle:
    """Test HookManager initialization, scanning, and reloading."""

    @pytest.mark.asyncio
    async def test_scan_default_paths(self, manager):
        # The fixture already sets search_dirs=[] to avoid loading real hooks
        manager.scan()
        # Calling twice should be fine
        manager.scan()

    @pytest.mark.asyncio
    async def test_reload_clears_registered_hooks(self, manager):
        async def my_hook(ctx):
            return HookResult(success=True)

        manager.add_hook(my_hook, events=[HookEvent.SESSION_START])

        # Verify it's there
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1

        # Reload should clear manually registered hooks. The fixture's
        # search_dirs=[] override already keeps this hermetic.
        manager.reload()
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        # Journaling hook is disabled in test fixture
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_search_directories_includes_various_locations(self, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        (fake_home / ".claude").mkdir()
        (fake_home / ".claude" / "hooks.json").touch()

        with patch("pathlib.Path.home", return_value=fake_home):
            # No search_dirs override, so this exercises the computed default.
            dirs = HookManager().search_dirs
            assert isinstance(dirs, list)
            assert any(".claude" in str(d) for d in dirs)

    @pytest.mark.asyncio
    async def test_get_search_directories_project_hierarchy(self, tmp_path):
        root = tmp_path / "root"
        leaf = root / "leaf"
        leaf.mkdir(parents=True)
        (root / ".zrb" / "hooks").mkdir(parents=True)
        (leaf / ".claude" / "hooks").mkdir(parents=True)

        with (
            patch("os.getcwd", return_value=str(leaf)),
            patch("pathlib.Path.cwd", return_value=leaf),
            patch.dict(os.environ, {"ZRB_ROOT_GROUP_NAME": "zrb"}),
        ):
            dirs = HookManager().search_dirs
            assert any("root/.zrb/hooks" in str(d) for d in dirs)
            assert any("leaf/.claude/hooks" in str(d) for d in dirs)

    @pytest.mark.asyncio
    async def test_get_search_directories_plugins(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "hooks").mkdir(parents=True)
        (plugin_dir / "hooks.json").touch()

        with patch("zrb.llm.hook.hook_loader.CFG") as mock_cfg:
            mock_cfg.ROOT_GROUP_NAME = "zrb"
            mock_cfg.LLM_PLUGIN_DIRS = [str(plugin_dir)]
            dirs = HookManager().search_dirs
            assert any(str(plugin_dir / "hooks") == str(d) for d in dirs)
            assert any(str(plugin_dir / "hooks.json") == str(d) for d in dirs)

    @pytest.mark.asyncio
    async def test_scan_recursive_depth_control(self, tmp_path):
        # Create nested hooks
        d1 = tmp_path / "d1"
        d2 = d1 / "d2"
        d2.mkdir(parents=True)
        (d2 / "h.json").write_text(
            json.dumps(
                [
                    {
                        "name": "deep-hook",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "echo 1"},
                    }
                ]
            )
        )

        # Default depth is usually 1, so d1 is scanned, but d2 might not be if depth is small
        manager = HookManager(max_depth=1)
        manager.scan(search_dirs=[str(tmp_path)])

        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        # depth 1: tmp_path (0) -> d1 (1). d2 is at depth 2 from tmp_path.
        assert len(results) == 0

        manager = HookManager(max_depth=2)
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1


class TestHookManagerRegistration:
    """Test manual hook registration behavior."""

    @pytest.mark.asyncio
    async def test_priority_sorting(self, manager):
        async def h1(ctx):
            return HookResult(success=True, output="P10")

        async def h2(ctx):
            return HookResult(success=True, output="P100")

        manager.add_hook(
            h1,
            config=HookConfig(
                name="low",
                events=[],
                type=HookType.COMMAND,
                config=CommandHookConfig(command=""),
                priority=10,
            ),
        )
        manager.add_hook(
            h2,
            config=HookConfig(
                name="high",
                events=[],
                type=HookType.COMMAND,
                config=CommandHookConfig(command=""),
                priority=100,
            ),
        )

        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert results[0].message == "P100"
        assert results[1].message == "P10"

    @pytest.mark.asyncio
    async def test_global_hooks_run_for_any_event(self, manager):
        executed = []

        async def global_hook(ctx):
            executed.append(ctx.event)
            return HookResult(success=True)

        manager.add_hook(global_hook)  # No events = global

        await manager.execute_hooks(HookEvent.SESSION_START, {})
        await manager.execute_hooks(HookEvent.NOTIFICATION, {})
        assert HookEvent.SESSION_START in executed
        assert HookEvent.NOTIFICATION in executed


class TestHookManagerExecution:
    """Test execution logic, error handling, and output formats."""

    @pytest.mark.asyncio
    async def test_blocking_hook_stops_execution(self, manager):
        executed = []

        async def blocking_hook(ctx):
            executed.append("blocking")
            return HookResult.block("Blocked by hook")

        async def subsequent_hook(ctx):
            executed.append("subsequent")
            return HookResult(success=True)

        # PRE_TOOL_USE is a blocking-capable event, so a block halts the chain.
        manager.add_hook(blocking_hook, events=[HookEvent.PRE_TOOL_USE])
        manager.add_hook(subsequent_hook, events=[HookEvent.PRE_TOOL_USE])

        results = await manager.execute_hooks(HookEvent.PRE_TOOL_USE, {})
        assert "blocking" in executed
        assert "subsequent" not in executed
        assert results[0].exit_code == 2

    @pytest.mark.asyncio
    async def test_block_on_non_blocking_event_continues_chain(self, manager):
        """exit-2 / decision=block is meaningless for a non-blocking event
        (e.g. Notification), so it must NOT suppress the remaining hooks
        (Claude-compatible)."""
        executed = []

        async def blocking_hook(ctx):
            executed.append("blocking")
            return HookResult.block("ignored here")

        async def subsequent_hook(ctx):
            executed.append("subsequent")
            return HookResult(success=True)

        manager.add_hook(blocking_hook, events=[HookEvent.NOTIFICATION])
        manager.add_hook(subsequent_hook, events=[HookEvent.NOTIFICATION])

        await manager.execute_hooks(HookEvent.NOTIFICATION, {})
        assert executed == ["blocking", "subsequent"]

    @pytest.mark.asyncio
    async def test_continue_false_stops_execution(self, manager):
        executed = []

        async def stop_hook(ctx):
            executed.append("stop")
            return HookResult(success=True, modifications={"continue": False})

        async def subsequent_hook(ctx):
            executed.append("subsequent")
            return HookResult(success=True)

        manager.add_hook(stop_hook, events=[HookEvent.SESSION_START])
        manager.add_hook(subsequent_hook, events=[HookEvent.SESSION_START])

        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert "stop" in executed
        assert "subsequent" not in executed
        assert results[0].continue_execution is False

    @pytest.mark.asyncio
    async def test_exception_handling(self, manager):
        async def failing_hook(ctx):
            raise ValueError("Intentional Failure")

        manager.add_hook(failing_hook, events=[HookEvent.SESSION_START])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1
        assert results[0].success is False
        assert "Intentional Failure" in results[0].message

    @pytest.mark.asyncio
    async def test_execute_hooks_simple_format(self, manager):
        hook = AsyncMock(return_value=HookResult(success=True, output="simple"))
        manager.add_hook(hook, events=[HookEvent.SESSION_START])

        results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})
        assert len(results) == 1
        assert results[0].output == "simple"

    @pytest.mark.asyncio
    async def test_execute_hooks_simple_modifications_mapping(self, manager):
        exec_result = HookExecutionResult(
            success=True,
            message="ok",
            decision="allow",
            reason="because",
            permission_decision="granted",
            permission_decision_reason="trusted",
            additional_context="more info",
            updated_input={"i": 1},
            system_message="sys",
            continue_execution=False,
            suppress_output=True,
            hook_specific_output={"o": 2},
        )

        with patch.object(manager, "execute_hooks", return_value=[exec_result]):
            results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})
            mods = results[0].modifications
            assert mods["decision"] == "allow"
            assert mods["reason"] == "because"
            assert mods["permissionDecision"] == "granted"
            assert mods["permissionDecisionReason"] == "trusted"
            assert mods["additionalContext"] == "more info"
            assert mods["updatedInput"] == {"i": 1}
            assert mods["systemMessage"] == "sys"
            assert mods["continue"] is False
            assert mods["suppressOutput"] is True
            assert mods["hookSpecificOutput"] == {"o": 2}


class TestHookManagerFormats:
    """Test loading hooks from various file formats."""

    @pytest.mark.asyncio
    async def test_load_json_list(self, manager, tmp_path):
        f = tmp_path / "hooks.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h1",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "echo 1"},
                    }
                ]
            )
        )
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_load_yaml_single(self, manager, tmp_path):
        f = tmp_path / "hook.yaml"
        f.write_text(
            "name: h2\nevents: [SessionStart]\ntype: command\nconfig: {command: 'echo 2'}"
        )
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_load_claude_nested_format(self, manager, tmp_path):
        f = tmp_path / "claude.json"
        data = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "bash",
                        "hooks": [{"type": "command", "command": "echo pre"}],
                    }
                ]
            }
        }
        f.write_text(json.dumps(data))
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(
            HookEvent.PRE_TOOL_USE, {"tool_name": "bash"}, tool_name="bash"
        )
        assert any("pre" in r.message for r in results)

    @pytest.mark.asyncio
    async def test_load_python_hook(self, manager, tmp_path):
        f = tmp_path / "test.hook.py"
        f.write_text(
            "from zrb.llm.hook.interface import HookResult\ndef register(manager):\n    async def h(ctx): return HookResult(success=True, output='py')\n    manager.add_hook(h, events=['SessionStart'])"
        )
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert any("py" in r.message for r in results)

    def test_load_python_hook_error_handling(self, manager, tmp_path):
        f = tmp_path / "bad.hook.py"
        f.write_text("raise Exception('load fail')")
        # Should not crash scan
        manager.scan(search_dirs=[str(tmp_path)])

    @pytest.mark.asyncio
    async def test_claude_format_invalid_event_and_type(self, manager, tmp_path):
        f = tmp_path / "bad_claude.json"
        data = {
            "hooks": {
                "UnknownEvent": [{"hooks": [{"type": "command", "command": "echo 1"}]}],
                "SessionStart": [{"hooks": [{"type": "unknown", "command": "echo 1"}]}],
            }
        }
        f.write_text(json.dumps(data))
        # Should not crash
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 0
