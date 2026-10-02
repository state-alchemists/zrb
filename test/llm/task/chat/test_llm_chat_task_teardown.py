import asyncio
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
    """Teardown must settle the manager the session's hooks actually ran on.

    Regression: it shut down the module-level singleton, but
    _create_llm_task_core builds a fresh HookManager per execution and that is
    the instance every hook is dispatched through — so the singleton held none of
    this session's tasks and detached async hooks outlived the session.
    """
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
@pytest.mark.parametrize("interrupt", [asyncio.CancelledError, KeyboardInterrupt])
async def test_interactive_teardown_finishes_before_reraising_an_interrupt(interrupt):
    """A Ctrl+C that interrupts SESSION_END — as a cancellation or as a
    KeyboardInterrupt — must not skip the rest of teardown: a speaker left
    open makes the exit wait out its drain, and hooks, subprocesses and
    executors would outlive the session."""
    from zrb.llm.util.feature_config import FeatureSessions

    closed: list[str] = []
    sessions = FeatureSessions(lambda: "speaker", closed.append)
    sessions.get("default")

    manager = MagicMock()
    manager.execute_hooks = AsyncMock(side_effect=interrupt)
    manager.shutdown = AsyncMock()
    task = LLMChatTask(name="teardown-task-interrupted")
    task.active_hook_manager = manager

    with (
        patch("zrb.llm.hook.executor.shutdown_hook_executor") as shutdown_executor,
        pytest.raises(interrupt),
    ):
        await task.teardown_interactive_resources()

    assert closed == ["speaker"]
    # The steps after SESSION_END still release their resources.
    manager.shutdown.assert_awaited_once_with(drain=True)
    shutdown_executor.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_interactive_teardown_holds_a_ctrl_c_while_closing_features():
    """A Ctrl+C landing while one feature closes must not leave the other
    features open, nor skip the teardown steps after them."""
    from zrb.llm.util.feature_config import FeatureSessions

    closed: list[str] = []

    def close(value: str) -> None:
        closed.append(value)
        raise KeyboardInterrupt

    speaker = FeatureSessions(lambda: "speaker", close)
    speaker.get("default")
    microphone = FeatureSessions(lambda: "microphone", close)
    microphone.get("default")

    manager = MagicMock()
    manager.execute_hooks = AsyncMock()
    manager.shutdown = AsyncMock()
    task = LLMChatTask(name="teardown-task-feature-interrupted")
    task.active_hook_manager = manager

    with (
        patch("zrb.llm.hook.executor.shutdown_hook_executor") as shutdown_executor,
        pytest.raises(KeyboardInterrupt),
    ):
        await task.teardown_interactive_resources()

    assert sorted(closed) == ["microphone", "speaker"]
    manager.shutdown.assert_awaited_once_with(drain=True)
    shutdown_executor.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_interactive_teardown_without_hook_manager_is_safe():
    """Teardown must not raise when no hook manager was set (e.g. session never
    reached _create_llm_task_core)."""
    task = LLMChatTask(name="teardown-task-none")
    # active_hook_manager defaults to None; teardown should be a no-op.
    await task.teardown_interactive_resources()
