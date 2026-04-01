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
        assert channel._waiting_for_edit_tool_call_id is None

    def test_is_waiting_for_edit_false(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        assert channel.is_waiting_for_edit() is False

    def test_is_waiting_for_edit_true(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        channel._waiting_for_edit_tool_call_id = "tool-123"
        assert channel.is_waiting_for_edit() is True

    def test_get_editing_args_no_waiting(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        assert channel.get_editing_args() is None

    def test_get_editing_args_with_context(self, mock_session_manager):
        from zrb.llm.approval.approval_channel import ApprovalContext
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        channel._waiting_for_edit_tool_call_id = "tool-123"
        channel._pending_context["tool-123"] = ApprovalContext(
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
            tool_call_id="tool-123",
        )
        result = channel.get_editing_args()
        assert result == {"arg1": "value1"}

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

    def test_handle_response_not_waiting_edit(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        channel._waiting_for_edit_tool_call_id = "tool-123"
        channel.handle_response("y")
        assert channel._waiting_for_edit_tool_call_id is None

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

    def test_parse_edited_content_plain_json(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        result = channel._parse_edited_content('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_edited_content_json_in_code_block(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        content = '```json\n{"key": "value"}\n```'
        result = channel._parse_edited_content(content)
        assert result == {"key": "value"}

    def test_parse_edited_content_invalid_json(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        result = channel._parse_edited_content("not valid json")
        assert result is None


class TestHTTPChatApprovalChannelWithFuture:
    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    def test_has_pending_approvals_true(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            channel._pending["tool-123"] = future
            assert channel.has_pending_approvals() is True
        finally:
            loop.close()

    def test_get_pending_approvals_with_data(self, mock_session_manager):
        from zrb.llm.approval.approval_channel import ApprovalContext
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            channel._pending["tool-123"] = future
            channel._pending_context["tool-123"] = ApprovalContext(
                tool_name="test_tool",
                tool_args={"arg1": "value1"},
                tool_call_id="tool-123",
            )
            result = channel.get_pending_approvals()
            assert len(result) == 1
            assert result[0]["tool_call_id"] == "tool-123"
            assert result[0]["tool_name"] == "test_tool"
        finally:
            loop.close()


class TestCreateHttpChatUiFactory:
    def test_create_http_chat_ui_factory(self):
        from zrb.runner.chat.http_chat import create_http_chat_ui_factory

        mock_manager = MagicMock()
        factory = create_http_chat_ui_factory(
            session_manager=mock_manager,
            session_id="test-session",
        )
        assert callable(factory)


class TestHTTPChatApprovalChannelApplyResponse:
    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    def test_apply_response_missing_id(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        channel._apply_response("nonexistent", "y")

    def test_parse_edited_content_yaml(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        channel = HTTPChatApprovalChannel(
            session_manager=mock_session_manager,
            session_id="test-session",
        )
        result = channel._parse_edited_content("key: value")
        assert result == {"key": "value"}
