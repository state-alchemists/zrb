"""Tests for the approval channel system."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolApproved

from zrb.llm.approval import ApprovalContext, TerminalApprovalChannel
from zrb.llm.ui.any_ui import AnyUI


@pytest.fixture
def mock_ui():
    """Create a mock UI for testing."""
    ui = MagicMock(spec=AnyUI)
    ui.ask_user = AsyncMock(return_value="y")
    return ui


class TestTerminalApprovalChannelWithHandler:
    """Tests for TerminalApprovalChannel with UI that has _tool_call_handler."""

    @pytest.mark.asyncio
    async def test_uses_ui_handler_with_formatters(self):
        """Test that TerminalApprovalChannel uses UI's _tool_call_handler when available."""
        mock_ui = MagicMock(spec=AnyUI)
        mock_ui.ask_user = AsyncMock(return_value="y")
        mock_ui.append_to_output = MagicMock()

        # Add a mock tool_call_handler with formatters
        mock_handler = MagicMock()
        mock_handler.format_approval_message = AsyncMock(return_value="Confirm message")
        mock_handler.get_response_handlers = MagicMock(return_value=[])
        mock_ui.tool_call_handler = mock_handler

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Write",
            tool_args={"path": "/tmp/test.txt", "content": "hello"},
            tool_call_id="call_handler_001",
        )

        result = await channel.request_approval(context)

        assert result.approved is True
        mock_ui.ask_user.assert_called_once()
        mock_handler.format_approval_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_edit_response_triggers_response_handler_chain(self):
        """Test that 'e' response triggers response handler chain."""
        mock_ui = MagicMock(spec=AnyUI)
        mock_ui.ask_user = AsyncMock(return_value="e")
        mock_ui.append_to_output = MagicMock()
        mock_ui.run_interactive_command = AsyncMock()

        # Add a mock tool_call_handler with response handlers
        mock_response_handler = AsyncMock()
        mock_response_handler.return_value = ToolApproved(override_args={"new": "args"})
        mock_handler = MagicMock()
        mock_handler.get_response_handlers = MagicMock(
            return_value=[mock_response_handler]
        )
        mock_handler.format_approval_message = AsyncMock(return_value="Confirm message")
        mock_ui.tool_call_handler = mock_handler

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Edit",
            tool_args={"path": "/tmp/test.txt", "old_text": "a", "new_text": "b"},
            tool_call_id="call_edit_001",
        )

        result = await channel.request_approval(context)

        # Should be approved with override args from response handler
        assert result.approved is True
        assert result.override_args == {"new": "args"}

    @pytest.mark.asyncio
    async def test_unknown_response_denies(self):
        """Test that unknown response denies the tool."""
        mock_ui = MagicMock(spec=AnyUI)
        mock_ui.ask_user = AsyncMock(return_value="unknown")
        mock_ui.append_to_output = MagicMock()

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={"command": "ls"},
            tool_call_id="call_unknown_001",
        )

        result = await channel.request_approval(context)

        assert result.approved is False
        assert "unknown" in result.message

    @pytest.mark.asyncio
    async def test_notify_calls_ui_append_to_output(self):
        """Test that notify method uses UI's append_to_output."""
        mock_ui = MagicMock(spec=AnyUI)
        mock_ui.append_to_output = MagicMock()

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_notify_001",
        )

        await channel.notify("Test message", context)

        mock_ui.append_to_output.assert_called_once_with("  Test message")

    @pytest.mark.asyncio
    async def test_edit_response_falls_back_to_handle_edit(self):
        """Test that 'e' response falls back to _handle_edit when no handler."""
        mock_ui = MagicMock(spec=AnyUI)
        mock_ui.ask_user = AsyncMock(return_value="e")
        mock_ui.append_to_output = MagicMock()
        mock_ui.run_interactive_command = AsyncMock(return_value=0)

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Edit",
            tool_args={"path": "/tmp/test.txt", "old_text": "a", "new_text": "b"},
            tool_call_id="call_edit_fallback_001",
        )

        result = await channel.request_approval(context)
        assert result is not None
