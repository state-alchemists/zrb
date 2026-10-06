import asyncio
import os
import shlex
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent

_PROCESS_STOP_TIMEOUT_SECONDS = 1.0


_PROCESS_STOP_POLL_SECONDS = 0.05


def _background_sleep_command(pid_path: str) -> str:
    'Start a long-lived child that records its own pid before sleeping.'
    script = (
        "import os, time, tempfile; "
        f"_d = os.path.dirname({pid_path!r}); "
        "_fd, _tmp = tempfile.mkstemp(dir=_d); "
        "os.write(_fd, str(os.getpid()).encode()); os.close(_fd); "
        f"os.replace(_tmp, {pid_path!r}); time.sleep(60)"
    )
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} & wait"


def _process_is_live(pid: int) -> bool:
    'Whether *pid* exists and is not a zombie awaiting reaping.'
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
    )
    return result.returncode == 0 and not result.stdout.lstrip().startswith("Z")


async def _assert_recorded_process_stops(pid_path: str) -> None:
    'A background child must not remain runnable after manager shutdown.'
    attempts = int(_PROCESS_STOP_TIMEOUT_SECONDS / _PROCESS_STOP_POLL_SECONDS)
    pid: int | None = None
    for _ in range(attempts):
        if os.path.exists(pid_path):
            with open(pid_path) as file:
                recorded = file.read().strip()



            if recorded:
                pid = int(recorded)
                if not _process_is_live(pid):
                    return
        await asyncio.sleep(_PROCESS_STOP_POLL_SECONDS)
    assert pid is None or not _process_is_live(
        pid
    ), "background descendant remained alive after manager shutdown"


def test_get_plugin_root_for_path_matches_builtin_plugin(monkeypatch):
    'A hook file under the built-in llm_plugin/ reports it as the plugin root.'
    from zrb.llm.hook import hook_loader

    monkeypatch.setattr(hook_loader.CFG, "LLM_PLUGIN_DIRS", [])
    builtin_hook = hook_loader.BUILTIN_PLUGIN_DIR / "hooks" / "hooks.json"

    result = hook_loader.get_plugin_root_for_path(builtin_hook)

    assert result == str(hook_loader.BUILTIN_PLUGIN_DIR.resolve())


def test_get_plugin_root_for_path_returns_none_outside_any_plugin_dir(
    tmp_path, monkeypatch
):
    """A hook loaded from a non-plugin tier (home/project/custom) has no
    plugin root — CLAUDE_PLUGIN_ROOT should stay empty for it."""
    from zrb.llm.hook import hook_loader

    monkeypatch.setattr(hook_loader.CFG, "LLM_PLUGIN_DIRS", [])
    unrelated_file = tmp_path / ".zrb" / "hooks.json"

    assert hook_loader.get_plugin_root_for_path(unrelated_file) is None


@pytest.mark.asyncio
async def test_shutdown_cancels_background_hooks_and_kills_their_subprocesses():
    'A detached async hook must not outlive the session that spawned it.'
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        pid_path = os.path.join(tmp, "child.pid")
        manager = HookManager(search_dirs=[])
        manager.parse_and_register(
            {
                "name": "slow-async",
                "events": ["Stop"],
                "type": "command",
                "async": True,


                "config": {
                    "command": _background_sleep_command(pid_path),
                    "shell": True,
                },
            },
            "test",
        )

        await manager.execute_hooks(HookEvent.STOP, {})
        assert manager.has_pending_background_hooks

        await manager.shutdown()

        await _assert_recorded_process_stops(pid_path)
        assert not manager.has_pending_background_hooks


@pytest.mark.asyncio
async def test_shutdown_is_a_noop_when_nothing_is_pending():
    manager = HookManager(search_dirs=[])
    await manager.shutdown()
    assert not manager.has_pending_background_hooks
    await manager.shutdown()


@pytest.mark.skipif(
    os.name != "posix",
    reason="chains `sleep; touch` with `;`, which cmd.exe does not parse",
)
@pytest.mark.asyncio
async def test_shutdown_drain_lets_a_quick_hook_finish_first():
    '`drain=True` is the per-run shape: finish, then cancel the stragglers.'
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sentinel = os.path.join(tmp, "finished")
        manager = HookManager(search_dirs=[])
        manager.parse_and_register(
            {
                "name": "quick-async",
                "events": ["Stop"],
                "type": "command",
                "async": True,
                "config": {"command": f"sleep 0.1; touch {sentinel}", "shell": True},
            },
            "test",
        )

        await manager.execute_hooks(HookEvent.STOP, {})
        await manager.shutdown(drain=True)

        assert os.path.exists(sentinel), "drain cancelled a hook that had time to run"
        assert not manager.has_pending_background_hooks


@pytest.mark.asyncio
async def test_shutdown_drain_still_cancels_a_hook_that_overruns_the_grace():
    """Draining is bounded — it must not become a way to block teardown."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        pid_path = os.path.join(tmp, "child.pid")
        manager = HookManager(search_dirs=[])
        manager.parse_and_register(
            {
                "name": "slow-async",
                "events": ["Stop"],
                "type": "command",
                "async": True,
                "config": {
                    "command": _background_sleep_command(pid_path),
                    "shell": True,
                },
            },
            "test",
        )

        await manager.execute_hooks(HookEvent.STOP, {})
        await manager.shutdown(grace_seconds=0.2, drain=True)

        await _assert_recorded_process_stops(pid_path)
        assert not manager.has_pending_background_hooks


@pytest.mark.asyncio
async def test_shutdown_drain_extends_for_an_agent_hooks_own_timeout():
    'An agent-type hook doing a real LLM round-trip legitimately needs'
    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "slow-judge",
            "events": ["Stop"],
            "type": "agent",
            "async": True,
            "timeout": 5,
            "config": {"system_prompt": "judge", "model": "fake-model"},
        },
        "test",
    )

    agent_instance = MagicMock()
    completed = False

    async def _slow_run(*args, **kwargs):
        nonlocal completed
        await asyncio.sleep(0.4)
        completed = True
        return MagicMock(output="done")

    agent_instance.run = AsyncMock(side_effect=_slow_run)
    agent_cls = MagicMock(return_value=agent_instance)

    with (
        patch("zrb.llm.hook.creator.resolve_configured_model") as mock_resolve_model,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_resolve_model.return_value = "resolved"
        await manager.execute_hooks(HookEvent.STOP, {})



        await manager.shutdown(grace_seconds=0.1, drain=True)

    assert completed, "agent hook was cancelled before its own timeout elapsed"


@pytest.mark.asyncio
async def test_per_run_hook_managers_are_isolated_from_the_developers_real_hooks():
    'Guard for the `_disable_real_filesystem_hooks` fixture in test/conftest.py.'
    import zrb.llm.task.building as llm_task_building
    import zrb.llm.task.chat.execution as chat_execution

    for module in (chat_execution, llm_task_building):
        manager = module.HookManager()
        for event in (HookEvent.NOTIFICATION, HookEvent.STOP, HookEvent.SESSION_END):
            results = await manager.execute_hooks(event, {})
            assert results == [], (
                f"{module.__name__} builds hook managers that run the real "
                f"filesystem hooks during tests (fired on {event})"
            )
        assert not manager.has_pending_background_hooks
