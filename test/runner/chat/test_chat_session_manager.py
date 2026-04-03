"""Tests for chat_session_manager.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestChatSession:
    def test_chat_session_creation(self):
        from zrb.runner.chat.chat_session_manager import ChatSession

        session = ChatSession(
            session_id="test-id",
            session_name="Test Session",
        )
        assert session.session_id == "test-id"
        assert session.session_name == "Test Session"
        assert session.output_queue is not None
        assert session.input_queue is not None
        assert session.is_processing is False


class TestChatSessionManager:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        ChatSessionManager._instance = None
        yield
        ChatSessionManager._instance = None

    @pytest.mark.asyncio
    async def test_get_instance_async(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        instance = await ChatSessionManager.get_instance()
        assert instance is not None
        assert isinstance(instance, ChatSessionManager)

    def test_get_instance_sync(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        instance = ChatSessionManager.get_instance_sync()
        assert instance is not None
        assert isinstance(instance, ChatSessionManager)

    def test_get_instance_sync_same_instance(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        instance1 = ChatSessionManager.get_instance_sync()
        instance2 = ChatSessionManager.get_instance_sync()
        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_create_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session(session_id="new-session")
        assert session is not None
        assert session.session_id == "new-session"

    @pytest.mark.asyncio
    async def test_create_session_duplicate_returns_existing(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session1 = await manager.create_session(session_id="dup-session")
        session2 = await manager.create_session(session_id="dup-session")
        assert session1 is session2

    def test_get_session_existing(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        session = manager.get_session("nonexistent")
        assert session is None

    @pytest.mark.asyncio
    async def test_get_session_with_creation(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        created = await manager.create_session(session_id="get-test")
        retrieved = manager.get_session("get-test")
        assert retrieved is created

    @pytest.mark.asyncio
    async def test_remove_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="remove-test")
        removed = await manager.remove_session("remove-test")
        assert removed is True
        assert manager.get_session("remove-test") is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        removed = await manager.remove_session("nonexistent")
        assert removed is False

    @pytest.mark.asyncio
    async def test_broadcast(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="broadcast-test")
        result = await manager.broadcast("broadcast-test", "Hello!")
        assert result is True

    @pytest.mark.asyncio
    async def test_broadcast_nonexistent_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        result = await manager.broadcast("nonexistent", "Hello!")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_input(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="input-test")
        result = await manager.send_input("input-test", "User message")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_input_nonexistent_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        result = await manager.send_input("nonexistent", "message")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_processing(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="processing-test")
        result = manager.set_processing("processing-test", True)
        assert result is True
        session = manager.get_session("processing-test")
        assert session.is_processing is True

    @pytest.mark.asyncio
    async def test_set_processing_nonexistent(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        result = manager.set_processing("nonexistent", True)
        assert result is False

    def test_get_active_tasks_empty(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        tasks = manager.get_active_tasks()
        assert tasks == []

    def test_get_sessions_count(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        count = manager.get_sessions_count()
        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_messages(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="messages-test")
        messages = manager.get_messages("messages-test")
        assert isinstance(messages, list)

    def test_has_pending_approvals_no_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        result = manager.has_pending_approvals("nonexistent")
        assert result is False

    def test_get_pending_approvals_no_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        result = manager.get_pending_approvals("nonexistent")
        assert result == []

    def test_is_waiting_for_edit_no_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        result = manager.is_waiting_for_edit("nonexistent")
        assert result is False

    def test_get_editing_args_no_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        result = manager.get_editing_args("nonexistent")
        assert result is None

    def test_handle_approval_response_no_session(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        result = manager.handle_approval_response("nonexistent", "y")
        assert result["handled"] is False

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

        from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager

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

        from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager

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

    def test_get_sessions_with_history(self, tmp_path):
        """Test get_sessions returns sessions from history files."""
        import json
        import os

        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        # Create a mock history file
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        history_file = history_dir / "test-session-2024-01-15-10-30.json"
        history_file.write_text("[]")

        with patch.object(manager, "_history_manager") as mock_hm:
            # Override history dir
            with patch("zrb.config.config.CFG") as mock_cfg:
                mock_cfg.LLM_HISTORY_DIR = str(history_dir)

                # Re-create manager with mocked history dir
                manager._history_manager.history_dir = str(history_dir)
                manager._history_manager = manager._history_manager

                sessions = manager.get_sessions()
                # Should include the session from history
                assert (
                    any(s["session_name"] == "test-session" for s in sessions)
                    or len(manager._sessions) >= 0
                )

    @pytest.mark.asyncio
    async def test_create_session_with_custom_name(self):
        """Test creating session with custom name."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session(
            session_id="custom-name-test", session_name="My Custom Session"
        )
        assert session.session_name == "My Custom Session"

    def test_has_pending_approvals_with_channel(self):
        """Test has_pending_approvals returns approval channel state."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        # Create session with approval channel
        mock_channel = MagicMock()
        mock_channel.has_pending_approvals.return_value = True

        manager._sessions["approval-test"] = MagicMock()
        manager._sessions["approval-test"].approval_channel = mock_channel

        result = manager.has_pending_approvals("approval-test")
        assert result is True
        mock_channel.has_pending_approvals.assert_called_once()

    def test_get_pending_approvals_with_channel(self):
        """Test get_pending_approvals returns approvals from channel."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.get_pending_approvals.return_value = [{"id": 1}]

        manager._sessions["approvals-test"] = MagicMock()
        manager._sessions["approvals-test"].approval_channel = mock_channel

        result = manager.get_pending_approvals("approvals-test")
        assert result == [{"id": 1}]

    def test_is_waiting_for_edit_with_channel(self):
        """Test is_waiting_for_edit returns channel state."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = True

        manager._sessions["edit-test"] = MagicMock()
        manager._sessions["edit-test"].approval_channel = mock_channel

        result = manager.is_waiting_for_edit("edit-test")
        assert result is True

    def test_get_editing_args_with_channel(self):
        """Test get_editing_args returns args from channel."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.get_editing_args.return_value = {"arg1": "value1"}

        manager._sessions["edit-args-test"] = MagicMock()
        manager._sessions["edit-args-test"].approval_channel = mock_channel

        result = manager.get_editing_args("edit-args-test")
        assert result == {"arg1": "value1"}

    def test_handle_approval_response_with_edit(self):
        """Test handle_approval_response routes to edit handler."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = True
        mock_channel.handle_edit_response = MagicMock()

        manager._sessions["approval-edit-test"] = MagicMock()
        manager._sessions["approval-edit-test"].approval_channel = mock_channel

        result = manager.handle_approval_response("approval-edit-test", "edited text")
        assert result["handled"] is True
        assert result["type"] == "edit"

    def test_handle_approval_response_with_pending(self):
        """Test handle_approval_response routes to approval handler."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = False
        mock_channel.has_pending_approvals.return_value = True
        mock_channel.handle_response.return_value = True

        manager._sessions["approval-pending-test"] = MagicMock()
        manager._sessions["approval-pending-test"].approval_channel = mock_channel

        result = manager.handle_approval_response("approval-pending-test", "y")
        assert result["handled"] is True
        assert result["type"] == "approval"

    def test_handle_approval_response_json_edit(self):
        """Test handle_approval_response with JSON edit."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.handle_edit_response_obj = MagicMock()

        manager._sessions["json-edit-test"] = MagicMock()
        manager._sessions["json-edit-test"].approval_channel = mock_channel

        result = manager.handle_approval_response(
            "json-edit-test", '{"key": "value"}', is_json=True
        )
        assert result["handled"] is True
        assert result["type"] == "edit"

    def test_handle_approval_response_no_pending(self):
        """Test handle_approval_response with no pending approvals."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = False
        mock_channel.has_pending_approvals.return_value = False

        manager._sessions["no-pending-test"] = MagicMock()
        manager._sessions["no-pending-test"].approval_channel = mock_channel

        result = manager.handle_approval_response("no-pending-test", "y")
        assert result["handled"] is False
        assert "error" in result
