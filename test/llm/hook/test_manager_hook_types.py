"""Tests for HookManager class using Public API."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def _fake_popen(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    """A Popen stand-in backed by real pipes already holding *stdout*/*stderr*.

    The hook reader drains file descriptors and stops at the child's exit, so a
    bare MagicMock whose ``communicate`` returns a tuple is not enough — it needs
    fds that can be selected on and an exit status that ``poll`` reports.
    """

    def _loaded(data: bytes):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, data)  # test payloads sit far under the 64 KiB buffer
        os.close(write_fd)  # so the reader sees EOF straight after the data
        return os.fdopen(read_fd, "rb")

    process = MagicMock()
    process.returncode = returncode
    process.stdin = None
    process.stdout = _loaded(stdout)
    process.stderr = _loaded(stderr)
    process.poll.return_value = returncode
    process.wait.return_value = returncode
    return process


@pytest.fixture
def manager():
    """Create HookManager for tests."""
    mock_cfg = MagicMock()
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.HOOKS_DIRS = []
    with patch("zrb.llm.hook.manager.CFG", mock_cfg):
        yield HookManager(search_dirs=[])


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

        mock_process = _fake_popen(stdout=b"blocked", returncode=2)

        with patch("subprocess.Popen", return_value=mock_process):
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

        mock_process = _fake_popen(stdout=b'{"k": "v"}')

        with patch("subprocess.Popen", return_value=mock_process):
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(HookEvent.SESSION_START, {})
            assert results[0].data["k"] == "v"

    @pytest.mark.asyncio
    async def test_command_hook_receives_command_env(self, manager, tmp_path):
        # PreCommand/PostCommand command hooks must see the parsed command via
        # CLAUDE_COMMAND_NAME / CLAUDE_COMMAND_ARGS.
        f = tmp_path / "h.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "name": "h",
                        "events": ["PreCommand"],
                        "type": "command",
                        "config": {"command": "true"},
                    }
                ]
            )
        )

        mock_process = _fake_popen()

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
            manager.scan(search_dirs=[str(tmp_path)])
            await manager.execute_hooks(
                HookEvent.PRE_COMMAND,
                {},
                command_name="/save",
                command_args="my-session",
            )

        env = mock_popen.call_args.kwargs["env"]
        assert env["CLAUDE_COMMAND_NAME"] == "/save"
        assert env["CLAUDE_COMMAND_ARGS"] == "my-session"

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

        loop = asyncio.get_running_loop()
        original_create_task = loop.create_task

        with patch("subprocess.Popen"):
            manager.scan(search_dirs=[str(tmp_path)])
            results = await manager.execute_hooks(HookEvent.SESSION_START, {})
            # Async command hooks are dispatched fire-and-forget on the running
            # loop: a task is spawned and no result is collected (they cannot
            # block or contribute context).
            assert len(manager.background_tasks) == 1
            assert results == []
            # Clean up: cancel the background task so it doesn't leak
            for task in manager.background_tasks:
                task.cancel()
            if manager.background_tasks:
                await asyncio.gather(*manager.background_tasks, return_exceptions=True)

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

        with patch("pydantic_ai.Agent", return_value=mock_agent):
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

        with patch("pydantic_ai.Agent", return_value=mock_agent):
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
