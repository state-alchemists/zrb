"""Tests for HookManager class using Public API."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from zrb.llm.hook.executor import HookExecutionResult
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import CommandHookConfig, HookConfig, MatcherConfig
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator


@pytest.fixture
def manager():
    return HookManager()


class TestHookManagerLifecycle:
    """Test HookManager initialization, scanning, and reloading."""

    @pytest.mark.asyncio
    async def test_scan_default_paths(self, manager):
        # Mocking search directories to be empty to avoid loading real hooks
        with patch.object(manager, "get_search_directories", return_value=[]):
            manager.scan()
            # Calling twice should be fine
            manager.scan()

    @pytest.mark.asyncio
    async def test_reload_clears_registered_hooks(self, manager):
        async def my_hook(ctx):
            return HookResult(success=True)

        manager.register(my_hook, events=[HookEvent.SESSION_START])

        # Verify it's there
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1

        # Reload should clear it (assuming no hooks found in default paths)
        with patch.object(manager, "get_search_directories", return_value=[]):
            manager.reload()
            results = await manager.execute_hooks(HookEvent.SESSION_START, {})
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_search_directories_includes_various_locations(
        self, manager, tmp_path
    ):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        (fake_home / ".claude").mkdir()
        (fake_home / ".claude" / "hooks.json").touch()

        with patch("pathlib.Path.home", return_value=fake_home):
            dirs = manager.get_search_directories()
            assert isinstance(dirs, list)
            assert any(".claude" in str(d) for d in dirs)

    @pytest.mark.asyncio
    async def test_get_search_directories_project_hierarchy(self, manager, tmp_path):
        root = tmp_path / "root"
        leaf = root / "leaf"
        leaf.mkdir(parents=True)
        (root / ".zrb" / "hooks").mkdir(parents=True)
        (leaf / ".claude" / "hooks").mkdir(parents=True)

        with patch("os.getcwd", return_value=str(leaf)), patch(
            "pathlib.Path.cwd", return_value=leaf
        ), patch.dict(os.environ, {"ZRB_ROOT_GROUP_NAME": "zrb"}):
            dirs = manager.get_search_directories()
            assert any("root/.zrb/hooks" in str(d) for d in dirs)
            assert any("leaf/.claude/hooks" in str(d) for d in dirs)

    @pytest.mark.asyncio
    async def test_get_search_directories_plugins(self, manager, tmp_path):
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "hooks").mkdir(parents=True)
        (plugin_dir / "hooks.json").touch()

        with patch("zrb.llm.hook.manager.CFG") as mock_cfg:
            mock_cfg.ROOT_GROUP_NAME = "zrb"
            mock_cfg.LLM_PLUGIN_DIRS = [str(plugin_dir)]
            dirs = manager.get_search_directories()
            assert any(str(plugin_dir / "hooks") == str(d) for d in dirs)
            assert any(str(plugin_dir / "hooks.json") == str(d) for d in dirs)

    @pytest.mark.asyncio
    async def test_scan_recursive_depth_control(self, manager, tmp_path):
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

        manager.register(
            h1,
            config=HookConfig(
                name="low",
                events=[],
                type=HookType.COMMAND,
                config=CommandHookConfig(command=""),
                priority=10,
            ),
        )
        manager.register(
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

        manager.register(global_hook)  # No events = global

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
    async def test_exception_handling(self, manager):
        async def failing_hook(ctx):
            raise ValueError("Intentional Failure")

        manager.register(failing_hook, events=[HookEvent.SESSION_START])
        results = await manager.execute_hooks(HookEvent.SESSION_START, {})
        assert len(results) == 1
        assert results[0].success is False
        assert "Intentional Failure" in results[0].message

    @pytest.mark.asyncio
    async def test_execute_hooks_simple_format(self, manager):
        hook = AsyncMock(return_value=HookResult(success=True, output="simple"))
        manager.register(hook, events=[HookEvent.SESSION_START])

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
            "from zrb.llm.hook.interface import HookResult\ndef register(manager):\n    async def h(ctx): return HookResult(success=True, output='py')\n    manager.register(h, events=['SessionStart'])"
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


class TestHookManagerHookTypes:
    """Test behavior of different hook types (Command, Prompt, Agent)."""

    @pytest.mark.asyncio
    async def test_command_hook_exit_codes(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "exit 2"},
                    }
                ]
            )
        )

        mock_process = MagicMock()
        mock_process.returncode = 2
        mock_process.communicate = AsyncMock(return_value=(b"blocked", b""))

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(HookEvent.SESSION_START, {})
            assert results[0].blocked is True
            assert "blocked" in results[0].message

    @pytest.mark.asyncio
    async def test_command_hook_json_output(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": 'echo \'{"k": "v"}\''},
                    }
                ]
            )
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'{"k": "v"}', b""))

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(HookEvent.SESSION_START, {})
            assert results[0].data["k"] == "v"

    @pytest.mark.asyncio
    async def test_command_hook_async(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "echo 1"},
                        "async": True,
                    }
                ]
            )
        )

        with patch("asyncio.create_subprocess_shell") as mock_shell, patch(
            "asyncio.create_task"
        ) as mock_create_task:
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(HookEvent.SESSION_START, {})
            assert "Async execution started" in results[0].message
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_hook(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "prompt",
                        "config": {
                            "user_prompt_template": "hi {{session_id}}",
                            "system_prompt": "s",
                        },
                    }
                ]
            )
        )

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(output='{"res": "ok"}'))

        with patch("pydantic_ai.Agent", return_value=mock_agent), patch(
            "pydantic_ai.models.openai.OpenAIModel", return_value=MagicMock()
        ):
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(
                HookEvent.SESSION_START, {}, session_id="sid"
            )
            assert results[0].data["res"] == "ok"
            mock_agent.run.assert_called_once()
            assert "hi sid" in mock_agent.run.call_args.args[0]

    @pytest.mark.asyncio
    async def test_agent_hook(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "agent",
                        "config": {"system_prompt": "s"},
                    }
                ]
            )
        )

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(output="agent output"))

        with patch("pydantic_ai.Agent", return_value=mock_agent), patch(
            "pydantic_ai.models.openai.OpenAIModel", return_value=MagicMock()
        ):
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(HookEvent.SESSION_START, "some input")
            assert results[0].message == "agent output"


class TestHookManagerMatchers:
    """Test matcher evaluation via Public API."""

    @pytest.mark.asyncio
    async def test_matcher_operators(self, manager, tmp_path):
        def create_hook(op, val):
            f = tmp_path / f"h_{op}.json"
            f.write_text(
                json.dumps(
                    [
                        {
                            "name": f"h_{op}",
                            "events": ["SessionStart"],
                            "type": "command",
                            "config": {"command": "echo 1"},
                            "matchers": [
                                {"field": "event_data", "operator": op, "value": val}
                            ],
                        }
                    ]
                )
            )

        create_hook("equals", "hello")
        create_hook("not_equals", "hello")
        create_hook("contains", "ell")
        create_hook("starts_with", "hel")
        create_hook("ends_with", "lo")
        create_hook("regex", "h.llo")
        create_hook("glob", "hel*")

        manager.scan(search_dirs=[str(tmp_path)])

        # Test Equals
        results = await manager.execute_hooks(HookEvent.SESSION_START, "hello")
        # Check that h_not_equals is skipped and h_equals is not
        skipped_names = [
            r.data.get("name")
            for r in results
            if r.message == "Skipped due to matchers"
        ]
        # Since HookManager doesn't put "name" in HookExecutionResult by default unless the hook returns it,
        # we have to rely on the fact that we registered 7 hooks and some should be skipped.
        # Let's check the number of skipped hooks.
        # "hello" matches: equals, contains, starts_with, ends_with, regex, glob.
        # "hello" does NOT match: not_equals.
        # So 1 should be skipped.
        assert sum(1 for r in results if r.message == "Skipped due to matchers") == 1

    @pytest.mark.asyncio
    async def test_matcher_case_insensitive(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "echo 1"},
                        "matchers": [
                            {
                                "field": "event_data",
                                "operator": "equals",
                                "value": "hello",
                                "case_sensitive": False,
                            }
                        ],
                    }
                ]
            )
        )
        manager.scan(search_dirs=[str(tmp_path)])
        results = await manager.execute_hooks(HookEvent.SESSION_START, "HELLO")
        assert all(r.message != "Skipped due to matchers" for r in results)

    @pytest.mark.asyncio
    async def test_matcher_nested_field_access(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "echo 1"},
                        "matchers": [
                            {
                                "field": "event_data.a.b",
                                "operator": "equals",
                                "value": 1,
                            }
                        ],
                    }
                ]
            )
        )
        manager.scan(search_dirs=[str(tmp_path)])

        class Obj:
            a = {"b": 1}

        results = await manager.execute_hooks(HookEvent.SESSION_START, Obj())
        assert all(r.message != "Skipped due to matchers" for r in results)

    @pytest.mark.asyncio
    async def test_matcher_edge_cases(self, manager, tmp_path):
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["SessionStart"],
                        "type": "command",
                        "config": {"command": "echo 1"},
                        "matchers": [
                            {
                                "field": "event_data",
                                "operator": "contains",
                                "value": "1",
                            },  # Should fail for int 123
                            {
                                "field": "event_data.boom",
                                "operator": "equals",
                                "value": 1,
                            },  # Attribute error
                        ],
                    }
                ]
            )
        )
        manager.scan(search_dirs=[str(tmp_path)])

        class Boom:
            @property
            def boom(self):
                raise AttributeError()

        results = await manager.execute_hooks(HookEvent.SESSION_START, 123)
        assert all(r.message == "Skipped due to matchers" for r in results)

        results = await manager.execute_hooks(HookEvent.SESSION_START, Boom())
        assert all(r.message == "Skipped due to matchers" for r in results)
