"""Tests for chat_session_manager.py."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_history_manager():
    with patch("zrb.runner.chat.chat_session_manager.FileHistoryManager") as mock_fhm:
        mock_fhm.return_value.load.return_value = []
        yield


class TestChatSessionManagerApprovals:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        ChatSessionManager.reset_instance()
        yield
        ChatSessionManager.reset_instance()

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
    async def test_has_pending_approvals_with_channel(self):
        """Test has_pending_approvals returns approval channel state."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        # Create session with approval channel
        mock_channel = MagicMock()
        mock_channel.has_pending_approvals.return_value = True

        session = await manager.create_session(
            session_id="approval-test", approval_channel=mock_channel
        )

        result = manager.has_pending_approvals("approval-test")
        assert result is True
        mock_channel.has_pending_approvals.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_approvals_with_channel(self):
        """Test get_pending_approvals returns approvals from channel."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.get_pending_approvals.return_value = [{"id": 1}]

        await manager.create_session(
            session_id="approvals-test", approval_channel=mock_channel
        )

        result = manager.get_pending_approvals("approvals-test")
        assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_is_waiting_for_edit_with_channel(self):
        """Test is_waiting_for_edit returns channel state."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = True

        await manager.create_session(
            session_id="edit-test", approval_channel=mock_channel
        )

        result = manager.is_waiting_for_edit("edit-test")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_editing_args_with_channel(self):
        """Test get_editing_args returns args from channel."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.get_editing_args.return_value = {"arg1": "value1"}

        await manager.create_session(
            session_id="edit-args-test", approval_channel=mock_channel
        )

        result = manager.get_editing_args("edit-args-test")
        assert result == {"arg1": "value1"}

    @pytest.mark.asyncio
    async def test_handle_approval_response_with_edit(self):
        """Test handle_approval_response routes to edit handler."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = True
        mock_channel.handle_edit_response = MagicMock()

        await manager.create_session(
            session_id="approval-edit-test", approval_channel=mock_channel
        )

        result = manager.handle_approval_response("approval-edit-test", "edited text")
        assert result["handled"] is True
        assert result["type"] == "edit"

    @pytest.mark.asyncio
    async def test_handle_approval_response_with_pending(self):
        """Test handle_approval_response routes to approval handler."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = False
        mock_channel.has_pending_approvals.return_value = True
        mock_channel.handle_response.return_value = True

        await manager.create_session(
            session_id="approval-pending-test", approval_channel=mock_channel
        )

        result = manager.handle_approval_response("approval-pending-test", "y")
        assert result["handled"] is True
        assert result["type"] == "approval"

    @pytest.mark.asyncio
    async def test_handle_approval_response_json_edit(self):
        """Test handle_approval_response with JSON edit."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = False
        mock_channel.handle_edit_response_obj = MagicMock()

        await manager.create_session(
            session_id="json-edit-test", approval_channel=mock_channel
        )

        result = manager.handle_approval_response(
            "json-edit-test", '{"key": "value"}', is_json=True
        )
        assert result["handled"] is True
        assert result["type"] == "edit"

    @pytest.mark.asyncio
    async def test_handle_approval_response_json_without_pending_edit(self):
        """Decoded args with no edit slot must not reach the approval handler.

        Regression: falling through handed the dict to handle_response, which
        cannot parse it and denied the pending approval outright — a client that
        raced edit-mode entry lost the tool call instead of retrying.
        """
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()

        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = False
        mock_channel.handle_edit_response_obj.return_value = False
        mock_channel.has_pending_approvals.return_value = True

        await manager.create_session(
            session_id="json-edit-stale-test", approval_channel=mock_channel
        )

        result = manager.handle_approval_response(
            "json-edit-stale-test", {"key": "value"}, is_json=True
        )
        assert result["handled"] is False
        mock_channel.handle_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_approval_response_no_pending_approvals(self):
        """When the channel has no pending approvals, handle returns the error fallback."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = False
        mock_channel.has_pending_approvals.return_value = False

        await manager.create_session(
            session_id="no-pending", approval_channel=mock_channel
        )
        result = manager.handle_approval_response("no-pending", "y")
        assert result["handled"] is False
        assert "No pending approvals" in result["error"]

    @pytest.mark.asyncio
    async def test_unconsumed_edit_response_falls_through_to_approval(self):
        """A stale edit slot must not report success for a dropped answer.

        The edit handler returning False means nothing consumed the response, so
        it has to reach the live pending approval instead of being swallowed.
        """
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = True
        mock_channel.handle_edit_response.return_value = False
        mock_channel.has_pending_approvals.return_value = True
        mock_channel.handle_response.return_value = True

        await manager.create_session(
            session_id="stale-edit", approval_channel=mock_channel
        )
        result = manager.handle_approval_response("stale-edit", "y")
        assert result == {"handled": True, "type": "approval"}
        mock_channel.handle_response.assert_called_once_with("y")

    @pytest.mark.asyncio
    async def test_unconsumed_edit_response_without_pending_reports_failure(self):
        """No consumer and nothing pending must surface as handled=False."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        mock_channel = MagicMock()
        mock_channel.is_waiting_for_edit.return_value = True
        mock_channel.handle_edit_response.return_value = False
        mock_channel.has_pending_approvals.return_value = False

        await manager.create_session(
            session_id="stale-edit-idle", approval_channel=mock_channel
        )
        result = manager.handle_approval_response("stale-edit-idle", "y")
        assert result["handled"] is False
