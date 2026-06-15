import asyncio
import json
import os
import time

import pytest

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent, HookType


@pytest.mark.asyncio
async def test_python_hook_execution():
    manager = HookManager(search_dirs=[])
    executed = []

    async def my_hook(context: HookContext) -> HookResult:
        executed.append(context)
        return HookResult(success=True)

    manager.register(my_hook, events=[HookEvent.SESSION_START])

    await manager.execute_hooks_simple(HookEvent.SESSION_START, {"test": "data"})

    assert len(executed) == 1
    assert executed[0].event == HookEvent.SESSION_START
    assert executed[0].event_data == {"test": "data"}


@pytest.mark.asyncio
async def test_hooks_globally_disabled_by_config(monkeypatch):
    """ZRB_HOOKS_ENABLED=off is a global kill-switch: no registered hook fires."""
    monkeypatch.setenv("ZRB_HOOKS_ENABLED", "off")
    manager = HookManager(search_dirs=[])
    fired = []

    async def my_hook(context: HookContext) -> HookResult:
        fired.append(context.event.value)
        return HookResult(success=True)

    manager.register(my_hook, events=[HookEvent.SESSION_START])

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert results == []
    assert fired == []

    # Flipping it back on (default) re-enables firing on the same manager.
    monkeypatch.setenv("ZRB_HOOKS_ENABLED", "on")
    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert len(results) == 1
    assert fired == ["SessionStart"]


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
    # Hooks will be lazily loaded on first execute_hooks call
    manager = HookManager(search_dirs=[hooks_dir])

    # Execute hooks using simple method for backward compatibility
    results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})

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
    manager = HookManager(search_dirs=[])

    async def modifier_hook(context: HookContext) -> HookResult:
        if context.event_data.get("tool") == "my_tool":
            return HookResult(
                success=True, modifications={"tool_args": {"extra_arg": "injected"}}
            )
        return HookResult(success=True)

    manager.register(modifier_hook, events=[HookEvent.PRE_TOOL_USE])

    results = await manager.execute_hooks_simple(
        HookEvent.PRE_TOOL_USE, {"tool": "my_tool", "args": {"original": "value"}}
    )

    assert len(results) == 1
    assert results[0].modifications["tool_args"] == {"extra_arg": "injected"}


@pytest.mark.asyncio
async def test_command_hook_receives_claude_event_json_on_stdin():
    """Command hooks get the Claude-shaped event payload on stdin.

    peon-ping and other Claude-Code-compatible hooks read their event from
    stdin (``json.load(sys.stdin)["hook_event_name"]``) and ignore env vars, so
    the payload must be written to the subprocess' stdin. ``cat`` echoes stdin
    back to stdout, which the executor surfaces as the result message.
    """
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
    """Hooks registered in Claude Code's settings.json (nested format) load.

    peon-ping installs itself into ``~/.claude/settings.json``, not hooks.json.
    Non-hook keys (model, permissions, …) must be ignored.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = {
        "model": "opus",  # non-hook key — must be ignored, not error
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


@pytest.mark.asyncio
async def test_command_hook_tolerates_tilde_and_missing_cwd():
    """A hook cwd with an unexpanded ``~`` (or a missing dir) must not crash.

    The OS does not expand ``~`` the way a shell does, so a display-formatted
    cwd like ``~/zrb`` used to fail with ``[Errno 2] No such file or directory``.
    It is now expanded, and a non-existent dir falls back to the inherited cwd.
    """
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
    assert (res[0].message or "").strip() == os.path.expanduser("~")

    res2 = await manager.execute_hooks(
        HookEvent.NOTIFICATION, {}, cwd="/no/such/dir/zzz"
    )
    assert res2 and res2[0].success  # missing dir → inherited cwd, no crash


@pytest.mark.asyncio
async def test_async_command_hook_is_non_blocking():
    """Async command hooks are fire-and-forget: execute_hooks returns without
    waiting for the subprocess. peon-ping marks its hooks ``async`` so a slow
    audio hook never stalls the agent (previously each one blocked the executor
    up to its timeout, producing the "Hook execution timed out" storm)."""
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
    assert results == []  # fire-and-forget contributes no result

    # Clean up: the background "sleep 5" subprocess must be killed before the
    # test ends, otherwise it leaks across tests.  Cancel the background task,
    # then wait with a short timeout — the CancelledError handler in the hook
    # kills the subprocess, but CPython's _make_subprocess_transport._wait()
    # can hang if cancellation hits mid-transport-init.  The timeout prevents
    # this hang from blocking the run.
    for task in manager._background_tasks:
        task.cancel()
    if manager._background_tasks:
        await asyncio.wait(
            manager._background_tasks,
            timeout=2.0,
            return_when=asyncio.ALL_COMPLETED,
        )


@pytest.mark.asyncio
async def test_sync_command_hook_is_killed_on_timeout():
    """A synchronous command hook that exceeds its timeout is killed and
    reported, instead of blocking the agent until the subprocess exits on its
    own (the thread-pool executor's own wait_for cannot interrupt the worker)."""
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


@pytest.mark.asyncio
async def test_command_hook_drops_oversized_env_value():
    """Oversized event_data is dropped from the subprocess environment, not
    passed to exec. event_data for SessionStart/Stop/SessionEnd can carry the
    whole message history; serialized into the env it overflowed the OS
    arg+env limit (``[Errno 7] Argument list too long``). The full payload is
    still delivered on stdin, so dropping the env copy is safe."""
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

    # ~1 MB of event_data — far over the per-value env cap.
    big = {"history": ["x" * 1000] * 1000}
    results = await manager.execute_hooks(HookEvent.STOP, big)

    assert results and results[0].success  # no E2BIG, hook ran
    assert "len=0" in (results[0].message or "")  # CLAUDE_EVENT_DATA was dropped


def test_get_search_directories_includes_claude_settings(tmp_path, monkeypatch):
    """``~/.claude/settings.json`` and ``settings.local.json`` are discovered."""
    from pathlib import Path

    from zrb.llm.hook import hook_loader

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}")
    (claude_dir / "settings.local.json").write_text("{}")

    # Pin both the home and cwd anchors to tmp_path so discovery is hermetic.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))

    dirs = hook_loader.get_search_directories()

    assert claude_dir / "settings.json" in dirs
    assert claude_dir / "settings.local.json" in dirs


def test_get_search_directories_dedups_home_and_project(tmp_path, monkeypatch):
    """When cwd is under $HOME, the home tier and the project upward-walk both
    visit $HOME — the result must contain no duplicate paths, else every
    ~/.claude hook would register and fire twice (e.g. two peon-ping toasts)."""
    from pathlib import Path

    from zrb.llm.hook import hook_loader

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}")
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: project))  # under home

    resolved = [str(Path(d).resolve()) for d in hook_loader.get_search_directories()]

    assert len(resolved) == len(set(resolved)), f"duplicate search paths: {resolved}"
    assert str((claude_dir / "settings.json").resolve()) in resolved
