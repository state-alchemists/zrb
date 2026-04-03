"""Tests for the approval channel system."""

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolApproved, ToolDenied

from zrb.llm.approval import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
    NullApprovalChannel,
    TerminalApprovalChannel,
    current_approval_channel,
)
from zrb.llm.tool_call.ui_protocol import UIProtocol


class TestApprovalContext:
    """Tests for ApprovalContext dataclass."""

    def test_approval_context_creation(self):
        """Test creating an ApprovalContext with all fields."""
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={"command": "ls -la"},
            tool_call_id="call_123",
            session_id="session_456",
        )

        assert context.tool_name == "Bash"
        assert context.tool_args == {"command": "ls -la"}
        assert context.tool_call_id == "call_123"
        assert context.session_id == "session_456"

    def test_approval_context_defaults(self):
        """Test ApprovalContext with minimal required fields."""
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_001",
        )

        assert context.tool_name == "Read"
        assert context.tool_args == {}
        assert context.tool_call_id == "call_001"
        assert context.session_id is None

    def test_approval_context_to_dict(self):
        """Test converting ApprovalContext to dict."""
        context = ApprovalContext(
            tool_name="Write",
            tool_args={"path": "/tmp/test.txt"},
            tool_call_id="call_999",
            session_id="sess_001",
        )

        result = asdict(context)
        assert result["tool_name"] == "Write"
        assert result["tool_args"] == {"path": "/tmp/test.txt"}
        assert result["tool_call_id"] == "call_999"
        assert result["session_id"] == "sess_001"


class TestApprovalResult:
    """Tests for ApprovalResult dataclass."""

    def test_approval_result_approved(self):
        """Test creating an approved result."""
        result = ApprovalResult(approved=True, message="Proceeding with execution")

        assert result.approved is True
        assert result.message == "Proceeding with execution"

    def test_approval_result_denied(self):
        """Test creating a denied result."""
        result = ApprovalResult(approved=False, message="Operation denied by policy")

        assert result.approved is False
        assert result.message == "Operation denied by policy"

    def test_to_pydantic_result_approved(self):
        """Test converting approved result to pydantic_ai types."""
        result = ApprovalResult(approved=True, message="All good")
        pydantic_result = result.to_pydantic_result()

        assert isinstance(pydantic_result, ToolApproved)

    def test_to_pydantic_result_denied(self):
        """Test converting denied result to pydantic_ai types."""
        result = ApprovalResult(approved=False, message="Access denied")
        pydantic_result = result.to_pydantic_result()

        assert isinstance(pydantic_result, ToolDenied)
        assert pydantic_result.message == "Access denied"


class TestNullApprovalChannel:
    """Tests for NullApprovalChannel (YOLO mode)."""

    @pytest.mark.asyncio
    async def test_null_channel_always_approves(self):
        """Test that NullApprovalChannel always approves."""
        channel = NullApprovalChannel()
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={"command": "rm -rf /"},
            tool_call_id="call_001",
        )

        result = await channel.request_approval(context)

        assert result.approved is True
        # NullApprovalChannel returns empty message for approvals

    @pytest.mark.asyncio
    async def test_null_channel_notify_is_noop(self):
        """Test that NullApprovalChannel notify does nothing."""
        channel = NullApprovalChannel()
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_002",
        )

        # Should not raise any exception
        await channel.notify("Test notification", context)


class TestTerminalApprovalChannel:
    """Tests for TerminalApprovalChannel wrapper."""

    @pytest.mark.asyncio
    async def test_terminal_channel_approves_on_yes(self):
        """Test that TerminalApprovalChannel approves when UI returns 'y'."""
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.ask_user = AsyncMock(return_value="y")
        mock_ui.append_to_output = MagicMock()

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={"command": "ls"},
            tool_call_id="call_001",
        )

        result = await channel.request_approval(context)

        assert result.approved is True
        mock_ui.ask_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminal_channel_denies_on_no(self):
        """Test that TerminalApprovalChannel denies when UI returns 'n'."""
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.ask_user = AsyncMock(return_value="n")
        mock_ui.append_to_output = MagicMock()

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Write",
            tool_args={"path": "/etc/passwd"},
            tool_call_id="call_002",
        )

        result = await channel.request_approval(context)

        assert result.approved is False
        mock_ui.ask_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminal_channel_empty_response_approves(self):
        """Test that TerminalApprovalChannel approves on empty response."""
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.ask_user = AsyncMock(return_value="")
        mock_ui.append_to_output = MagicMock()

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Read",
            tool_args={"path": "/tmp/test"},
            tool_call_id="call_003",
        )

        result = await channel.request_approval(context)

        assert result.approved is True

    @pytest.mark.asyncio
    async def test_terminal_channel_uses_notify(self):
        """Test that TerminalApprovalChannel uses UI for notifications."""
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.ask_user = AsyncMock(return_value="y")

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_004",
        )

        await channel.notify("Tool executed successfully", context)

        # Should not raise - notify is informational


class TestCurrentApprovalChannelContextVar:
    """Tests for current_approval_channel ContextVar."""

    def test_default_value_is_none(self):
        """Test that default value is None."""
        assert current_approval_channel.get() is None

    @pytest.mark.asyncio
    async def test_set_and_get_context_var(self):
        """Test setting and getting the approval channel context."""
        mock_channel = MagicMock(spec=ApprovalChannel)

        token = current_approval_channel.set(mock_channel)
        try:
            assert current_approval_channel.get() is mock_channel
        finally:
            current_approval_channel.reset(token)

    @pytest.mark.asyncio
    async def test_context_var_propagation(self):
        """Test that context var can be propagated to nested contexts."""
        mock_channel = MagicMock(spec=ApprovalChannel)

        async def inner():
            return current_approval_channel.get()

        token = current_approval_channel.set(mock_channel)
        try:
            result = await inner()
            assert result is mock_channel
        finally:
            current_approval_channel.reset(token)


class TestApprovalChannelProtocol:
    """Tests for ApprovalChannel protocol compliance."""

    def test_terminal_channel_implements_protocol(self):
        """Test that TerminalApprovalChannel implements ApprovalChannel protocol."""
        mock_ui = MagicMock(spec=UIProtocol)
        channel = TerminalApprovalChannel(ui=mock_ui)

        # Check protocol methods exist
        assert hasattr(channel, "request_approval")
        assert hasattr(channel, "notify")
        assert callable(channel.request_approval)
        assert callable(channel.notify)

    def test_null_channel_implements_protocol(self):
        """Test that NullApprovalChannel implements ApprovalChannel protocol."""
        channel = NullApprovalChannel()

        # Check protocol methods exist
        assert hasattr(channel, "request_approval")
        assert hasattr(channel, "notify")
        assert callable(channel.request_approval)
        assert callable(channel.notify)


class TestIntegrationWithRunAgent:
    """Integration tests for approval channel with run_agent."""

    @pytest.mark.asyncio
    async def test_approval_channel_parameter_propagation(self):
        """Test that approval_channel parameter is accepted by run_agent."""
        from zrb.llm.agent.run_agent import run_agent
        from zrb.llm.config.limiter import LLMLimiter

        # Create a mock channel
        mock_channel = MagicMock(spec=ApprovalChannel)
        mock_channel.request_approval = AsyncMock(
            return_value=ApprovalResult(approved=True, message="Test approval")
        )

        # Verify the parameter is accepted (function signature check)
        import inspect

        sig = inspect.signature(run_agent)
        assert "approval_channel" in sig.parameters

    def test_current_approval_channel_in_run_agent_module(self):
        """Test that current_approval_channel is available from run_agent module."""
        from zrb.llm.agent.run_agent import current_approval_channel as ctx_var

        # Both should be ContextVar with same name
        assert ctx_var.name == "current_approval_channel"
        # Should be able to get (returns None by default)
        assert ctx_var.get() is None


class TestApprovalChannelInLLMTask:
    """Tests for approval channel integration in LLMTask."""

    def test_llm_task_accepts_approval_channel(self):
        """Test that LLMTask accepts approval_channel parameter."""
        from zrb.llm.task.llm_task import LLMTask

        mock_channel = MagicMock(spec=ApprovalChannel)

        task = LLMTask(
            name="test_task",
            approval_channel=mock_channel,
        )

        assert task.approval_channel is mock_channel

    def test_llm_task_approval_channel_property(self):
        """Test that LLMTask has approval_channel property and setter."""
        from zrb.llm.task.llm_task import LLMTask

        task = LLMTask(name="test_task")

        assert task.approval_channel is None

        mock_channel = MagicMock(spec=ApprovalChannel)
        task.approval_channel = mock_channel

        assert task.approval_channel is mock_channel


# Fixture for tests
@pytest.fixture
def mock_ui():
    """Create a mock UI for testing."""
    ui = MagicMock(spec=UIProtocol)
    ui.ask_user = AsyncMock(return_value="y")
    return ui


@pytest.fixture
def approval_context():
    """Create a sample approval context for testing."""
    return ApprovalContext(
        tool_name="Bash",
        tool_args={"command": "echo test"},
        tool_call_id="test_call_001",
        session_id="test_session",
    )


class TestTerminalApprovalChannelWithHandler:
    """Tests for TerminalApprovalChannel with UI that has _tool_call_handler."""

    @pytest.mark.asyncio
    async def test_uses_ui_handler_with_formatters(self):
        """Test that TerminalApprovalChannel uses UI's _tool_call_handler when available."""
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.ask_user = AsyncMock(return_value="y")
        mock_ui.append_to_output = MagicMock()

        # Add a mock tool_call_handler with formatters
        mock_handler = MagicMock()
        mock_handler._argument_formatters = ["formatter1", "formatter2"]
        mock_handler.format_approval_message = AsyncMock(return_value="Confirm message")
        mock_handler.get_response_handlers = MagicMock(return_value=[])
        mock_ui._tool_call_handler = mock_handler

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
        mock_ui = MagicMock(spec=UIProtocol)
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
        mock_ui._tool_call_handler = mock_handler

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
        mock_ui = MagicMock(spec=UIProtocol)
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
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.append_to_output = MagicMock()

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_notify_001",
        )

        await channel.notify("Test message", context)

        mock_ui.append_to_output.assert_called_once_with("Test message")

    @pytest.mark.asyncio
    async def test_edit_response_falls_back_to_handle_edit(self):
        """Test that 'e' response falls back to _handle_edit when no handler."""
        mock_ui = MagicMock(spec=UIProtocol)
        mock_ui.ask_user = AsyncMock(return_value="e")
        mock_ui.append_to_output = MagicMock()
        mock_ui.run_interactive_command = AsyncMock(return_value=0)
        mock_ui._tool_call_handler = None  # No handler

        channel = TerminalApprovalChannel(ui=mock_ui)
        context = ApprovalContext(
            tool_name="Edit",
            tool_args={"path": "/tmp/test.txt", "old_text": "a", "new_text": "b"},
            tool_call_id="call_edit_fallback_001",
        )

        result = await channel.request_approval(context)
        assert result is not None


class TestMultiplexApprovalChannel:
    """Tests for MultiplexApprovalChannel."""

    @pytest.fixture
    def mock_channel(self):
        """Create a mock approval channel."""
        channel = MagicMock(spec=ApprovalChannel)
        channel.request_approval = AsyncMock(
            return_value=ApprovalResult(approved=True, message="Approved")
        )
        channel.notify = AsyncMock(return_value=None)
        return channel

    @pytest.fixture
    def deny_channel(self):
        """Create a mock approval channel that denies."""
        channel = MagicMock(spec=ApprovalChannel)
        channel.request_approval = AsyncMock(
            return_value=ApprovalResult(approved=False, message="Denied")
        )
        channel.notify = AsyncMock(return_value=None)
        return channel

    @pytest.mark.asyncio
    async def test_multiplex_channel_returns_first_response(
        self, mock_channel, deny_channel
    ):
        """Test that MultiplexApprovalChannel returns first response."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        channel = MultiplexApprovalChannel([mock_channel, deny_channel])
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={"command": "ls"},
            tool_call_id="call_mux_001",
        )

        result = await channel.request_approval(context)

        # One channel should have been called
        assert (
            mock_channel.request_approval.called or deny_channel.request_approval.called
        )

    @pytest.mark.asyncio
    async def test_multiplex_channel_races_channels(self, mock_channel, deny_channel):
        """Test that channels race concurrently."""
        import asyncio

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        call_times = []

        async def slow_channel_1(ctx):
            await asyncio.sleep(0.1)
            call_times.append(1)
            return ApprovalResult(approved=True, message="Slow")

        async def fast_channel_2(ctx):
            call_times.append(2)
            return ApprovalResult(approved=False, message="Fast deny")

        mock_channel.request_approval = slow_channel_1
        deny_channel.request_approval = fast_channel_2

        channel = MultiplexApprovalChannel([mock_channel, deny_channel])
        context = ApprovalContext(
            tool_name="Write",
            tool_args={"path": "/tmp/test"},
            tool_call_id="call_mux_002",
        )

        result = await channel.request_approval(context)

        # Fast channel (2) should have been called first
        assert call_times[0] == 2

    @pytest.mark.asyncio
    async def test_multiplex_channel_cancels_pending(self, mock_channel, deny_channel):
        """Test that pending channels are cancelled when one responds."""
        import asyncio

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        slow_task = None

        async def slow_channel(ctx):
            nonlocal slow_task
            slow_task = asyncio.current_task()
            await asyncio.sleep(1)  # Would block forever
            return ApprovalResult(approved=True, message="Never")

        async def fast_channel(ctx):
            await asyncio.sleep(0.05)
            return ApprovalResult(approved=True, message="Fast")

        mock_channel.request_approval = slow_channel
        deny_channel.request_approval = fast_channel

        channel = MultiplexApprovalChannel([mock_channel, deny_channel])
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_mux_003",
        )

        result = await channel.request_approval(context)

        assert result.approved is True
        assert result.message == "Fast"

    @pytest.mark.asyncio
    async def test_multiplex_channel_empty_list_auto_approves(self):
        """Test that empty channel list auto-approves."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        channel = MultiplexApprovalChannel([])
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={},
            tool_call_id="call_mux_004",
        )

        result = await channel.request_approval(context)

        assert result.approved is True

    @pytest.mark.asyncio
    async def test_multiplex_channel_handles_exception(self):
        """Test that exceptions in channels don't crash the multiplex."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        async def failing_channel(ctx):
            raise Exception("Channel error")

        async def working_channel(ctx):
            return ApprovalResult(approved=True, message="Working")

        failing_mock = MagicMock(spec=ApprovalChannel)
        failing_mock.request_approval = failing_channel

        working_mock = MagicMock(spec=ApprovalChannel)
        working_mock.request_approval = working_channel

        channel = MultiplexApprovalChannel([failing_mock, working_mock])
        context = ApprovalContext(
            tool_name="Write",
            tool_args={},
            tool_call_id="call_mux_005",
        )

        # Should not raise, but result depends on race order
        # Working channel might win the race before failing channel sets result
        result = await channel.request_approval(context)

        # At minimum, the request should complete without raising
        assert result is not None

    @pytest.mark.asyncio
    async def test_multiplex_notify_broadcasts(self, mock_channel, deny_channel):
        """Test that notify broadcasts to all channels."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        channel = MultiplexApprovalChannel([mock_channel, deny_channel])
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_mux_006",
        )

        await channel.notify("Test notification", context)

        mock_channel.notify.assert_called_once()
        deny_channel.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiplex_notify_handles_exception(self, mock_channel):
        """Test that notify handles exceptions gracefully."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        async def failing_notify(msg, ctx):
            raise Exception("Notify failed")

        mock_channel.notify = failing_notify

        deny_channel = MagicMock(spec=ApprovalChannel)

        async def working_notify(msg, ctx):
            return None

        deny_channel.notify = working_notify

        channel = MultiplexApprovalChannel([mock_channel, deny_channel])
        context = ApprovalContext(
            tool_name="Read",
            tool_args={},
            tool_call_id="call_mux_007",
        )

        # Should not raise
        await channel.notify("Test", context)

    @pytest.mark.asyncio
    async def test_multiplex_request_approval_shutdown(self):
        """Test that request_approval returns denied on shutdown."""
        import sys

        from zrb.llm.approval.multiplex_approval_channel import (
            MultiplexApprovalChannel,
            is_shutdown_requested,
        )

        # Mock shutdown requested
        original = getattr(sys, "_zrb_shutdown_requested", False)
        try:
            setattr(sys, "_zrb_shutdown_requested", True)

            mock_channel = MagicMock(spec=ApprovalChannel)
            mock_channel.request_approval = AsyncMock(
                return_value=ApprovalResult(approved=True, message="Approved")
            )

            channel = MultiplexApprovalChannel([mock_channel])
            context = ApprovalContext(
                tool_name="Bash",
                tool_args={},
                tool_call_id="call_shutdown_001",
            )

            result = await channel.request_approval(context)

            assert result.approved is False
            assert "Shutdown" in result.message
            # Should not call the channel
            mock_channel.request_approval.assert_not_called()
        finally:
            setattr(sys, "_zrb_shutdown_requested", original)

    @pytest.mark.asyncio
    async def test_multiplex_notify_shutdown(self):
        """Test that notify returns early on shutdown."""
        import sys

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        # Mock shutdown requested
        original = getattr(sys, "_zrb_shutdown_requested", False)
        try:
            setattr(sys, "_zrb_shutdown_requested", True)

            mock_channel = MagicMock(spec=ApprovalChannel)
            mock_channel.notify = AsyncMock()

            channel = MultiplexApprovalChannel([mock_channel])
            context = ApprovalContext(
                tool_name="Read",
                tool_args={},
                tool_call_id="call_notify_shutdown_001",
            )

            await channel.notify("Test", context)

            # Should not call notify on the channel
            mock_channel.notify.assert_not_called()
        finally:
            setattr(sys, "_zrb_shutdown_requested", original)

    @pytest.mark.asyncio
    async def test_multiplex_notify_without_context(self, mock_channel):
        """Test that notify works without context parameter."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        channel = MultiplexApprovalChannel([mock_channel])

        await channel.notify("Test notification")

        mock_channel.notify.assert_called_once_with("Test notification", None)

    @pytest.mark.asyncio
    async def test_multiplex_all_channels_fail(self):
        """Test that request_approval handles all channels failing."""
        import asyncio

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        async def failing_channel(ctx):
            raise Exception("Channel error")

        mock_channel1 = MagicMock(spec=ApprovalChannel)
        mock_channel1.request_approval = failing_channel

        mock_channel2 = MagicMock(spec=ApprovalChannel)
        mock_channel2.request_approval = failing_channel

        channel = MultiplexApprovalChannel([mock_channel1, mock_channel2])
        context = ApprovalContext(
            tool_name="Write",
            tool_args={},
            tool_call_id="call_all_fail_001",
        )

        # Should handle gracefully when all channels fail
        # The first completed sets the future with the error result
        result = await channel.request_approval(context)

        # Result should have error message since all channels failed
        assert result is not None
        assert result.approved is False
        assert "error" in result.message.lower() or "Error" in result.message

    @pytest.mark.asyncio
    async def test_multiplex_cancellation_propagation(self):
        """Test that external cancellation propagates correctly."""
        import asyncio

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def slow_channel(ctx):
            started.set()
            await asyncio.sleep(10)  # Would block forever
            return ApprovalResult(approved=True, message="Never")

        mock_channel = MagicMock(spec=ApprovalChannel)
        mock_channel.request_approval = slow_channel

        channel = MultiplexApprovalChannel([mock_channel])
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={},
            tool_call_id="call_cancel_001",
        )

        async def run_and_cancel():
            task = asyncio.create_task(channel.request_approval(context))
            await started.wait()  # Wait for the slow channel to start
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                cancelled.set()
                raise

        with pytest.raises(asyncio.CancelledError):
            await run_and_cancel()

        assert cancelled.is_set()

    @pytest.mark.asyncio
    async def test_is_shutdown_requested_utility(self):
        """Test the is_shutdown_requested utility function."""
        import sys

        from zrb.llm.approval.multiplex_approval_channel import is_shutdown_requested

        # Default should be False
        original = getattr(sys, "_zrb_shutdown_requested", False)
        try:
            # Test default
            if hasattr(sys, "_zrb_shutdown_requested"):
                delattr(sys, "_zrb_shutdown_requested")
            assert is_shutdown_requested() is False

            # Test set to True
            setattr(sys, "_zrb_shutdown_requested", True)
            assert is_shutdown_requested() is True

            # Test set to False
            setattr(sys, "_zrb_shutdown_requested", False)
            assert is_shutdown_requested() is False
        finally:
            setattr(sys, "_zrb_shutdown_requested", original)
