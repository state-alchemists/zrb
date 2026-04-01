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
