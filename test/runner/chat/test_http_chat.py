"""Tests for http_chat.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHTTPChatApprovalChannel:
    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    def test_initialization(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        assert channel.session_id == "test-session"
        assert channel.session_manager is mock_session_manager

    def test_is_waiting_for_edit_false(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        assert channel.is_waiting_for_edit() is False

    def test_get_editing_args_no_waiting(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        assert channel.get_editing_args() is None

    def test_debug_state(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        state = channel.debug_state()
        assert "waiting_for_edit_id" in state
        assert "pending_keys" in state
        assert "pending_context_keys" in state

    def test_has_pending_approvals_false(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        assert channel.has_pending_approvals() is False

    def test_get_pending_approvals_empty(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        result = channel.get_pending_approvals()
        assert result == []

    def test_handle_response_no_pending(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        result = channel.handle_response("y")
        assert result is False

    def test_handle_edit_response_no_waiting(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        channel.handle_edit_response("y")
        assert mock_session_manager.broadcast.call_count == 0

    def test_handle_edit_response_obj_no_waiting(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        channel.handle_edit_response_obj({"arg1": "value"})
        assert mock_session_manager.broadcast.call_count == 0


class TestHTTPChatApprovalChannelWithData:
    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_pending_approvals_lifecycle(self, mock_session_manager):
        from zrb.llm.approval.approval_channel import ApprovalContext
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )

        ctx = ApprovalContext(
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
            tool_call_id="tool-123",
        )

        # request_approval is public
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        assert channel.has_pending_approvals() is True
        pending = channel.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0]["tool_name"] == "test_tool"

        # handle_response is public
        channel.handle_response("y", "tool-123")
        result = await task
        assert result.approved is True
        assert channel.has_pending_approvals() is False


class TestCreateHttpChatUiFactory:
    def test_create_http_chat_ui_factory(self):
        from zrb.runner.chat.http_chat import create_http_chat_ui_factory

        mock_manager = MagicMock()
        factory = create_http_chat_ui_factory(
            session_manager=mock_manager,
            session_id="test-session",
        )
        assert callable(factory)


class TestHTTPChatApprovalChannelMore:
    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def channel(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        return HTTPChatApprovalChannel(mock_session_manager, "sess1")

    @pytest.mark.asyncio
    async def test_request_approval_and_cancel(self, channel):
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool1", {"k": "v"}, "id1")

        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        assert channel.has_pending_approvals()

        # Cancel it
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert not channel.has_pending_approvals()

    @pytest.mark.asyncio
    async def test_notify(self, channel, mock_session_manager):
        await channel.notify("hello")
        mock_session_manager.broadcast.assert_called_with("sess1", "hello")

    @pytest.mark.asyncio
    async def test_handle_edit_response(self, channel):
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        # Start edit mode via handle_response
        channel.handle_response("e", "id1")
        assert channel.is_waiting_for_edit()

        # handle_edit_response is public
        channel.handle_edit_response('{"a": 1}')

        res = await task
        assert res.approved is True
        assert res.override_args == {"a": 1}
        assert not channel.is_waiting_for_edit()

    @pytest.mark.asyncio
    async def test_handle_edit_response_obj(self, channel):
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        channel.handle_response("e", "id1")
        # handle_edit_response_obj is public
        channel.handle_edit_response_obj({"b": 2})

        res = await task
        assert res.approved is True
        assert res.override_args == {"b": 2}
