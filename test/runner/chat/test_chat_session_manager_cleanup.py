"""Tests for chat_session_manager.py."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_history_manager():
    with patch("zrb.runner.chat.chat_session_manager.FileHistoryManager") as mock_fhm:
        mock_fhm.return_value.load.return_value = []
        yield


class TestChatSessionManagerCleanup:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        ChatSessionManager.reset_instance()
        yield
        ChatSessionManager.reset_instance()

    @pytest.mark.asyncio
    async def test_remove_session_clears_its_activity_registry_bucket(self):
        """Removing a session must not leave its (now-empty) activity bucket
        behind in agent_activity_registry -- one dict entry per session_id
        ever seen would otherwise accumulate for the process's life."""
        from zrb.llm.agent.activity import agent_activity_registry
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        before = agent_activity_registry.tracked_session_count()
        await manager.create_session(session_id="leak-test")
        agent_activity_registry.start("agent-1", "researcher", session_id="leak-test")
        agent_activity_registry.finish("agent-1", session_id="leak-test")
        assert agent_activity_registry.tracked_session_count() == before + 1

        await manager.remove_session("leak-test")

        assert agent_activity_registry.tracked_session_count() == before

    @pytest.mark.asyncio
    async def test_remove_session_clears_its_live_subagent_session_bucket(self):
        """Same leak, same fix, for the "talk to a running sub-agent
        directly" registry (live_session.py) -- it must not outlive session
        teardown either."""
        from zrb.llm.agent.subagent.live_session import live_subagent_session_registry
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        before = live_subagent_session_registry.tracked_session_count()
        await manager.create_session(session_id="live-leak-test")
        live_subagent_session_registry.add_session(
            "live-leak-test", "agent-1", "researcher", MagicMock(), MagicMock()
        )
        assert live_subagent_session_registry.tracked_session_count() == before + 1

        await manager.remove_session("live-leak-test")

        assert live_subagent_session_registry.tracked_session_count() == before

    @pytest.mark.asyncio
    async def test_remove_session_cleans_up_its_background_shell_processes(
        self, tmp_path
    ):
        """A background Shell(background=True) process this session started
        must not outlive session removal -- the per-message teardown
        deliberately skips it (it must survive across messages in the same
        session), and full-shutdown cancellation never reached it either."""
        from zrb.llm.tool.ambient_state import current_chat_session_id
        from zrb.llm.tool.shell import run_shell_command
        from zrb.llm.tool.shell_background import get_shell_background_registry
        from zrb.runner.chat.chat_session_manager import ChatSessionManager
        from zrb.util.contextvar_scope import scoped

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="bg-leak-test")
        with scoped(current_chat_session_id, "bg-leak-test"):
            msg = await run_shell_command(
                "sleep 30", background=True, cwd=str(tmp_path)
            )
        handle = msg.split("Handle:")[1].split(".")[0].strip()

        await manager.remove_session("bg-leak-test")

        registry = get_shell_background_registry()
        result = await registry.collect(handle)
        assert "Unknown handle" in result

    @pytest.mark.asyncio
    async def test_remove_session_does_not_kill_another_sessions_process_with_the_same_name(
        self, tmp_path
    ):
        """Regression: `session_name` is a client-supplied display label
        `create_session` never enforces unique -- two different, concurrently
        active sessions CAN share one. Cleanup must key off the unique
        session_id, never that name, or removing one session could kill a
        same-named session's still-running background process."""
        from zrb.llm.tool.ambient_state import current_chat_session_id
        from zrb.llm.tool.shell import run_shell_command
        from zrb.llm.tool.shell_background import get_shell_background_registry
        from zrb.runner.chat.chat_session_manager import ChatSessionManager
        from zrb.util.contextvar_scope import scoped

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(
            session_id="dup-name-a", session_name="shared-display-name"
        )
        await manager.create_session(
            session_id="dup-name-b", session_name="shared-display-name"
        )

        with scoped(current_chat_session_id, "dup-name-a"):
            msg_a = await run_shell_command(
                "sleep 30", background=True, cwd=str(tmp_path)
            )
        with scoped(current_chat_session_id, "dup-name-b"):
            msg_b = await run_shell_command(
                "sleep 30", background=True, cwd=str(tmp_path)
            )
        handle_a = msg_a.split("Handle:")[1].split(".")[0].strip()
        handle_b = msg_b.split("Handle:")[1].split(".")[0].strip()

        await manager.remove_session("dup-name-a")

        registry = get_shell_background_registry()
        result_a = await registry.collect(handle_a)
        assert "Unknown handle" in result_a
        result_b = registry.poll(handle_b)
        assert "running" in result_b
        await registry.kill(handle_b)

    def test_get_active_tasks_empty(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        tasks = manager.get_active_tasks()
        assert tasks == []

    @pytest.mark.asyncio
    async def test_cancel_all_sessions(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="cancel-test")
        await manager.cancel_all_sessions()

    @pytest.mark.asyncio
    async def test_cancel_all_sessions_with_running_task(self):
        """Test canceling sessions with active task coroutines."""
        import asyncio

        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        # Create a session with a running task coroutine
        async def long_running():
            await asyncio.sleep(100)

        session = await manager.create_session(session_id="cancel-with-task")
        task = asyncio.create_task(long_running())
        session.task_coroutine = task

        # Add another session without task
        await manager.create_session(session_id="cancel-no-task")

        # Cancel all sessions
        await manager.cancel_all_sessions()

        # Verify task was cancelled
        assert task.cancelled() or task.done()

    def test_get_active_tasks_with_running_task(self):
        """Test get_active_tasks returns tasks that are still running."""
        import asyncio

        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        # Create async task in event loop
        async def create_session_with_task():
            session = await manager.create_session(session_id="active-task-test")

            async def running():
                await asyncio.sleep(100)

            task = asyncio.create_task(running())
            session.task_coroutine = task
            return task

        # Run in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            task = loop.run_until_complete(create_session_with_task())
            active_tasks = manager.get_active_tasks()
            assert len(active_tasks) == 1
            assert active_tasks[0] == task
            # Cancel the task
            task.cancel()
            loop.run_until_complete(asyncio.sleep(0))
            # Now task should not be in active list
            active_tasks = manager.get_active_tasks()
            assert len(active_tasks) == 0
        finally:
            loop.close()

    @pytest.mark.asyncio
    async def test_remove_session_cancels_running_task(self):
        """An in-flight task gets cancelled before the session is dropped."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session(session_id="cancellable")

        async def _hang():
            await asyncio.sleep(60)

        session.task_coroutine = asyncio.create_task(_hang())
        await asyncio.sleep(0.01)

        removed = await manager.remove_session("cancellable")
        assert removed is True
        assert manager.get_session("cancellable") is None
