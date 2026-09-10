"""Tests for chat_session_manager.py."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_history_manager():
    with patch("zrb.runner.chat.chat_session_manager.FileHistoryManager") as mock_fhm:
        mock_fhm.return_value.load.return_value = []
        yield


class TestParseDelegatedSession:
    """`parse_delegated_session`: recognizes the delegate.py naming shape."""

    def test_ordinary_name_returns_none(self):
        from zrb.runner.chat.chat_session_manager import parse_delegated_session

        assert parse_delegated_session("my-project-chat") is None

    def test_delegated_name_extracts_parent_and_agent(self):
        from zrb.runner.chat.chat_session_manager import parse_delegated_session

        result = parse_delegated_session("sess1-sub-researcher-deadbeef")
        assert result == ("sess1", "researcher")

    def test_hyphenated_agent_name_still_parses(self):
        """agent names like 'code-reviewer' must not confuse the greedy match."""
        from zrb.runner.chat.chat_session_manager import parse_delegated_session

        result = parse_delegated_session("my-sess-sub-code-reviewer-0123abcd")
        assert result == ("my-sess", "code-reviewer")

    def test_short_id_suffix_does_not_match(self):
        """The agent_id suffix must be exactly 8 hex chars, matching
        `uuid.uuid4().hex[:8]` — a shorter/longer tail is not this shape."""
        from zrb.runner.chat.chat_session_manager import parse_delegated_session

        assert parse_delegated_session("sess1-sub-researcher-abc") is None


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

        ChatSessionManager.reset_instance()
        yield
        ChatSessionManager.reset_instance()

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
    async def test_send_input_queues_message_and_attachments(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session(session_id="input-attach-test")
        await manager.send_input(
            "input-attach-test", "look at this", attachments=["/tmp/a.png"]
        )
        queued = session.input_queue.get_nowait()
        assert queued == {"message": "look at this", "attachments": ["/tmp/a.png"]}

    @pytest.mark.asyncio
    async def test_send_input_defaults_to_no_attachments(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session(session_id="input-no-attach-test")
        await manager.send_input("input-no-attach-test", "hello")
        queued = session.input_queue.get_nowait()
        assert queued == {"message": "hello", "attachments": []}

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

    @pytest.mark.asyncio
    async def test_create_session_with_custom_name(self):
        """Test creating session with custom name."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session(
            session_id="custom-name-test", session_name="My Custom Session"
        )
        assert session.session_name == "My Custom Session"

    @pytest.mark.asyncio
    async def test_has_session_true_and_false(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="exists")
        assert manager.has_session("exists") is True
        assert manager.has_session("absent") is False

    @pytest.mark.asyncio
    async def test_sessions_property_returns_dict(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="s1")
        sessions = manager.sessions
        assert "s1" in sessions

    @pytest.mark.asyncio
    async def test_create_session_with_no_session_id_generates_random(self):
        """Passing session_id=None triggers the random-name branch."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        session = await manager.create_session()
        assert session.session_id  # truthy
