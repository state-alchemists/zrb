import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.task.chat.task import LLMChatTask


@pytest.mark.asyncio
async def test_interactive_teardown_fires_terminal_session_end():
    """SESSION_END fires once when the interactive chat session tears down
    (Claude-compatible: terminal, not per-turn)."""
    from zrb.llm.hook.interface import HookContext, HookResult
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

    fired: list[str] = []

    async def record(context: HookContext) -> HookResult:
        fired.append(context.event.value)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.SESSION_END])

    task = LLMChatTask(name="teardown-task")
    task.active_hook_manager = manager

    await task.teardown_interactive_resources()

    assert fired == ["SessionEnd"]


@pytest.mark.asyncio
async def test_interactive_teardown_shuts_down_the_session_hook_manager():
    """Teardown settles the per-run hook manager, not the module singleton."""
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

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
    await manager.execute_hooks(HookEvent.STOP, {})
    assert manager.has_pending_background_hooks

    task = LLMChatTask(name="teardown-task-bg")
    task.active_hook_manager = manager

    await task.teardown_interactive_resources()

    assert not manager.has_pending_background_hooks


@pytest.mark.asyncio
async def test_a_cancelled_interactive_teardown_still_runs_to_the_end():
    """A Ctrl+C cancelling teardown mid-step still lets every step run."""
    from zrb.llm.util.feature_config import FeatureSessions

    closed: list[str] = []
    sessions = FeatureSessions(lambda: "speaker", closed.append)
    sessions.get("default")

    session_end_started = asyncio.Event()
    finish_session_end = asyncio.Event()
    finished: list[str] = []

    async def session_end(*_args: object, **_kwargs: object) -> None:
        session_end_started.set()
        await finish_session_end.wait()
        finished.append("SessionEnd")

    manager = MagicMock()
    manager.execute_hooks = AsyncMock(side_effect=session_end)
    manager.shutdown = AsyncMock()
    task = LLMChatTask(name="teardown-task-cancelled")
    task.active_hook_manager = manager

    with patch("zrb.llm.hook.executor.shutdown_hook_executor") as shutdown_executor:
        teardown = asyncio.create_task(task.teardown_interactive_resources())
        await session_end_started.wait()
        teardown.cancel()
        await asyncio.sleep(0)
        teardown.cancel()
        await asyncio.sleep(0)
        finish_session_end.set()
        with pytest.raises(asyncio.CancelledError):
            await teardown

    assert finished == ["SessionEnd"]
    assert closed == ["speaker"]
    manager.shutdown.assert_awaited_once()
    assert manager.shutdown.await_args.kwargs["drain"] is True
    shutdown_executor.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_interactive_teardown_without_hook_manager_is_safe():
    """Teardown does not raise when no hook manager was set."""
    task = LLMChatTask(name="teardown-task-none")
    await task.teardown_interactive_resources()


def _register_sleeper(manager, name: str, event: str, *, is_async: bool) -> None:
    manager.parse_and_register(
        {
            "name": name,
            "events": [event],
            "type": "command",
            "async": is_async,
            "config": {"command": "sleep 30", "shell": True},
        },
        "test",
    )


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="uses POSIX `sleep`")
async def test_a_slow_session_end_hook_is_cancelled_at_the_exit_budget(monkeypatch):
    from zrb.config.config import CFG
    from zrb.llm.hook.manager import HookManager

    monkeypatch.setattr(CFG, "HOOKS_EXIT_TIMEOUT", 300)
    manager = HookManager(search_dirs=[])
    _register_sleeper(manager, "slow-session-end", "SessionEnd", is_async=False)
    task = LLMChatTask(name="teardown-slow-session-end")
    task.active_hook_manager = manager

    started = time.monotonic()
    with patch("zrb.llm.hook.executor.shutdown_hook_executor"):
        await task.teardown_interactive_resources()

    # Its own timeout is 600 s; the budget, plus the kill, is what it gets.
    assert time.monotonic() - started < 10


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="uses POSIX `sleep`")
async def test_session_end_and_detached_hooks_share_one_exit_budget(monkeypatch):
    from zrb.config.config import CFG
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

    monkeypatch.setattr(CFG, "HOOKS_EXIT_TIMEOUT", 300)
    manager = HookManager(search_dirs=[])
    _register_sleeper(manager, "slow-detached", "Stop", is_async=True)
    _register_sleeper(manager, "slow-session-end", "SessionEnd", is_async=False)
    await manager.execute_hooks(HookEvent.STOP, {})
    task = LLMChatTask(name="teardown-shared-budget")
    task.active_hook_manager = manager

    with (
        patch.object(manager, "shutdown", wraps=manager.shutdown) as shutdown,
        patch("zrb.llm.hook.executor.shutdown_hook_executor"),
    ):
        await task.teardown_interactive_resources()

    # SessionEnd used the budget up, so the detached hook gets no drain time.
    assert shutdown.await_args.kwargs["drain_seconds"] < 0.3
    assert not manager.has_pending_background_hooks
