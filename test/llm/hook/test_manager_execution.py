import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_python_hook_execution():
    manager = HookManager(search_dirs=[])
    executed = []

    async def my_hook(context: HookContext) -> HookResult:
        executed.append(context)
        return HookResult(success=True)

    manager.add_hook(my_hook, events=[HookEvent.SESSION_START])

    await manager.execute_hooks_simple(HookEvent.SESSION_START, {"test": "data"})

    assert len(executed) == 1
    assert executed[0].event == HookEvent.SESSION_START
    assert executed[0].event_data == {"test": "data"}


@pytest.mark.asyncio
async def test_hook_factory_fires_on_first_lazy_access_not_just_manual_scan():
    'Lazy execution runs factories before the first hook access.'
    manager = HookManager(search_dirs=[])
    registered = []

    def factory(mgr):
        registered.append(mgr)

    manager.add_hook_factory(factory)
    await manager.execute_hooks(HookEvent.NOTIFICATION, {})

    assert registered == [manager]


def test_reload_runs_each_factory_exactly_once():
    'Reload runs each factory exactly once.'
    manager = HookManager(search_dirs=[])
    call_count = 0

    def factory(mgr):
        nonlocal call_count
        call_count += 1

    manager.add_hook_factory(factory)
    manager.reload()

    assert call_count == 1


@pytest.mark.asyncio
async def test_hooks_globally_disabled_by_config(monkeypatch):
    'ZRB_HOOKS_ENABLED=off is a global kill-switch: no registered hook fires.'
    monkeypatch.setenv("ZRB_HOOKS_ENABLED", "off")
    manager = HookManager(search_dirs=[])
    fired = []

    async def my_hook(context: HookContext) -> HookResult:
        fired.append(context.event.value)
        return HookResult(success=True)

    manager.add_hook(my_hook, events=[HookEvent.SESSION_START])

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert results == []
    assert fired == []


    monkeypatch.setenv("ZRB_HOOKS_ENABLED", "on")
    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert len(results) == 1
    assert fired == ["SessionStart"]


@pytest.mark.asyncio
async def test_config_file_loading_and_hydration(tmp_path):

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



    manager = HookManager(search_dirs=[hooks_dir])


    results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})


    assert len(results) >= 1
    found = False
    for res in results:
        if res.output and "Hello from file" in res.output:
            found = True
            break
    assert found


@pytest.mark.asyncio
async def test_pre_tool_use_modification():
    manager = HookManager(search_dirs=[])

    async def modifier_hook(context: HookContext) -> HookResult:
        if context.event_data.get("tool") == "my_tool":
            return HookResult(
                success=True, modifications={"tool_args": {"extra_arg": "injected"}}
            )
        return HookResult(success=True)

    manager.add_hook(modifier_hook, events=[HookEvent.PRE_TOOL_USE])

    results = await manager.execute_hooks_simple(
        HookEvent.PRE_TOOL_USE, {"tool": "my_tool", "args": {"original": "value"}}
    )

    assert len(results) == 1
    assert results[0].modifications["tool_args"] == {"extra_arg": "injected"}


@pytest.mark.asyncio
async def test_command_hook_receives_claude_event_json_on_stdin():
    'Command hooks get the Claude-shaped event payload on stdin.'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "echo-stdin",
            "events": ["SessionStart"],
            "type": "command",
            "config": {"command": "cat", "shell": True},
        },
        "test",
    )

    results = await manager.execute_hooks(
        HookEvent.SESSION_START, {"k": "v"}, session_id="sess-123"
    )

    received = None
    for res in results:
        if res.message and res.message.strip().startswith("{"):
            received = json.loads(res.message)
            break
    assert received is not None, "command hook produced no JSON payload on stdout"
    assert received["hook_event_name"] == "SessionStart"
    assert received["session_id"] == "sess-123"


@pytest.mark.asyncio
async def test_claude_settings_json_hooks_are_loaded(tmp_path):
    "Hooks registered in Claude Code's settings.json (nested format) load."
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = {
        "model": "opus",
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "echo 'from settings'"}]}
            ]
        },
    }
    with open(claude_dir / "settings.json", "w") as f:
        json.dump(settings, f)

    manager = HookManager(search_dirs=[claude_dir / "settings.json"])
    results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})

    assert any(r.output and "from settings" in r.output for r in results)


def _to_msys_path(path: str) -> str:
    "`C:\\Users\\x` -> `/c/Users/x`, matching Git-for-Windows coreutils'"
    drive, rest = os.path.splitdrive(path)
    if not drive:
        return path
    return f"/{drive[0].lower()}{rest.replace(os.sep, '/')}"


@pytest.mark.asyncio
async def test_command_hook_tolerates_tilde_and_missing_cwd():
    'Expand ``~`` and tolerate a missing hook working directory.'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "pwd-hook",
            "events": ["Notification"],
            "type": "command",
            "config": {"command": "pwd", "shell": True},
        },
        "test",
    )

    res = await manager.execute_hooks(HookEvent.NOTIFICATION, {}, cwd="~")
    assert res and res[0].success
    expected = os.path.expanduser("~")
    actual = (res[0].message or "").strip()
    if os.name == "nt":





        assert actual in (expected, _to_msys_path(expected))
    else:
        assert actual == expected

    res2 = await manager.execute_hooks(
        HookEvent.NOTIFICATION, {}, cwd="/no/such/dir/zzz"
    )
    assert res2 and res2[0].success


@pytest.mark.asyncio
async def test_async_command_hook_is_non_blocking():
    'Async command hooks return without waiting for the subprocess.'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "slow-async",
            "events": ["Stop"],
            "type": "command",
            "async": True,
            "config": {"command": "sleep 5", "shell": True},
        },
        "test",
    )

    start = time.monotonic()
    results = await manager.execute_hooks(HookEvent.STOP, {})
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"async hook blocked for {elapsed:.2f}s"
    assert results == []





    await manager.shutdown()


@pytest.mark.asyncio
async def test_async_agent_hook_is_non_blocking():
    'An async agent-type Stop hook is backgrounded the same way an async'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "slow-judge",
            "events": ["Stop"],
            "type": "agent",
            "async": True,
            "config": {"system_prompt": "judge", "model": "fake-model"},
        },
        "test",
    )

    agent_instance = MagicMock()

    async def _slow_run(*args, **kwargs):
        await asyncio.sleep(5)
        return MagicMock(output="done")

    agent_instance.run = AsyncMock(side_effect=_slow_run)
    agent_cls = MagicMock(return_value=agent_instance)

    with (
        patch("zrb.llm.hook.creator.resolve_configured_model") as mock_resolve_model,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_resolve_model.return_value = "resolved"
        start = time.monotonic()
        results = await manager.execute_hooks(HookEvent.STOP, {})
        elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"async agent hook blocked for {elapsed:.2f}s"
    assert results == []

    await manager.shutdown()


@pytest.mark.asyncio
async def test_sync_command_hook_is_killed_on_timeout():
    'A synchronous command hook that exceeds its timeout is killed and'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "slow-sync",
            "events": ["PreToolUse"],
            "type": "command",
            "timeout": 1,
            "config": {"command": "sleep 30", "shell": True},
        },
        "test",
    )

    start = time.monotonic()
    results = await manager.execute_hooks(HookEvent.PRE_TOOL_USE, {})
    elapsed = time.monotonic() - start

    assert elapsed < 15, f"timed-out hook was not capped: {elapsed:.2f}s"
    assert results and results[0].success is False
    combined = (results[0].message or "") + (results[0].error or "")
    assert "timed out" in combined.lower()


@pytest.mark.skipif(
    os.name != "posix",
    reason="`${#VAR}` is POSIX parameter expansion; cmd.exe echoes it verbatim",
)
@pytest.mark.asyncio
async def test_command_hook_drops_oversized_env_value():
    'Oversized event_data is dropped from the subprocess environment, not'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "envcheck",
            "events": ["Stop"],
            "type": "command",
            "timeout": 5,
            "config": {"command": "echo len=${#CLAUDE_EVENT_DATA}", "shell": True},
        },
        "test",
    )


    big = {"history": ["x" * 1000] * 1000}
    results = await manager.execute_hooks(HookEvent.STOP, big)

    assert results and results[0].success
    assert "len=0" in (results[0].message or "")


def test_get_search_directories_includes_claude_settings(tmp_path, monkeypatch):
    '``~/.claude/settings.json`` and ``settings.local.json`` are discovered.'
    from pathlib import Path

    from zrb.llm.hook import hook_loader

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}")
    (claude_dir / "settings.local.json").write_text("{}")


    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))

    dirs = hook_loader.get_search_directories()

    assert claude_dir / "settings.json" in dirs
    assert claude_dir / "settings.local.json" in dirs


def test_get_search_directories_dedups_home_and_project(tmp_path, monkeypatch):
    'When cwd is under $HOME, the home tier and the project upward-walk both'
    from pathlib import Path

    from zrb.llm.hook import hook_loader

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}")
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: project))

    resolved = [str(Path(d).resolve()) for d in hook_loader.get_search_directories()]

    assert len(resolved) == len(set(resolved)), f"duplicate search paths: {resolved}"
    assert str((claude_dir / "settings.json").resolve()) in resolved


def test_get_plugin_root_for_path_matches_configured_plugin_dir(tmp_path, monkeypatch):
    'A hook file under a configured LLM_PLUGIN_DIRS entry reports that entry'
    from zrb.llm.hook import hook_loader

    plugin_dir = tmp_path / "my-plugin"
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_file = hooks_dir / "hooks.json"
    hook_file.write_text("[]")

    monkeypatch.setattr(hook_loader.CFG, "LLM_PLUGIN_DIRS", [str(plugin_dir)])

    assert hook_loader.get_plugin_root_for_path(hook_file) == str(plugin_dir.resolve())
