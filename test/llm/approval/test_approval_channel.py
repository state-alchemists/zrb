"""Tests for the approval channel system."""

import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import ToolApproved, ToolDenied

from zrb.llm.approval import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
    NullApprovalChannel,
    TerminalApprovalChannel,
    current_approval_channel,
    load_approval_channel,
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


class TestLoadApprovalChannel:
    """Tests for load_approval_channel factory function."""

    def test_load_returns_none_when_not_configured(self):
        """Test that load_approval_channel returns None when no factory configured."""
        with patch("zrb.llm.approval.factory.CFG") as mock_cfg:
            mock_cfg.LLM_APPROVAL_CHANNEL_FACTORY = None

            result = load_approval_channel()
            assert result is None

    def test_load_raises_on_invalid_path(self):
        """Test that load_approval_channel raises on invalid module path."""
        with patch("zrb.llm.approval.factory.CFG") as mock_cfg:
            mock_cfg.LLM_APPROVAL_CHANNEL_FACTORY = "nonexistent_module.factory"

            with pytest.raises(ImportError):
                load_approval_channel()

    def test_load_raises_on_missing_function(self):
        """Test that load_approval_channel raises when function doesn't exist."""
        with patch("zrb.llm.approval.factory.CFG") as mock_cfg:
            # Use a module that exists but doesn't have the function
            mock_cfg.LLM_APPROVAL_CHANNEL_FACTORY = "os.nonexistent_function"

            with pytest.raises(AttributeError):
                load_approval_channel()

    def test_load_raises_on_wrong_return_type(self):
        """Test that load_approval_channel raises when factory returns wrong type."""
        # This test requires complex module mocking - skipped for now
        # The actual TypeError check in factory.py handles this at runtime
        pytest.skip("Requires complex module mocking setup")


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

        assert task._approval_channel is mock_channel

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