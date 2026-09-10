"""Tests for the approval channel system."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.approval import AnyApprovalChannel, ApprovalContext, ApprovalResult


class TestMultiplexApprovalChannel:
    """Tests for MultiplexApprovalChannel."""

    @pytest.fixture
    def mock_channel(self):
        """Create a mock approval channel."""
        channel = MagicMock(spec=AnyApprovalChannel)
        channel.request_approval = AsyncMock(
            return_value=ApprovalResult(approved=True, message="Approved")
        )
        channel.notify = AsyncMock(return_value=None)
        return channel

    @pytest.fixture
    def deny_channel(self):
        """Create a mock approval channel that denies."""
        channel = MagicMock(spec=AnyApprovalChannel)
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
    async def test_multiplex_channel_empty_list_denies(self):
        """An empty channel list has nothing to ask, so it must deny rather
        than fail open and auto-approve."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        channel = MultiplexApprovalChannel([])
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={},
            tool_call_id="call_mux_004",
        )

        result = await channel.request_approval(context)

        assert result.approved is False
        assert result.message == "No approval channels configured"

    @pytest.mark.asyncio
    async def test_multiplex_channel_handles_exception(self):
        """Test that exceptions in channels don't crash the multiplex."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        async def failing_channel(ctx):
            raise Exception("Channel error")

        async def working_channel(ctx):
            return ApprovalResult(approved=True, message="Working")

        failing_mock = MagicMock(spec=AnyApprovalChannel)
        failing_mock.request_approval = failing_channel

        working_mock = MagicMock(spec=AnyApprovalChannel)
        working_mock.request_approval = working_channel

        channel = MultiplexApprovalChannel([failing_mock, working_mock])
        context = ApprovalContext(
            tool_name="Write",
            tool_args={},
            tool_call_id="call_mux_005",
        )

        result = await channel.request_approval(context)

        # Deterministic: an errored channel never resolves the race, so the
        # working channel's answer always wins regardless of ordering.
        assert result.approved is True
        assert result.message == "Working"

    @pytest.mark.asyncio
    async def test_multiplex_failing_channel_does_not_win_race(self):
        """A channel that raises immediately must not deny before a slower
        (human) channel gets to answer."""
        import asyncio

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        async def broken_channel(ctx):
            raise Exception("bad token")

        async def human_channel(ctx):
            await asyncio.sleep(0.05)
            return ApprovalResult(approved=True, message="Human approved")

        broken = MagicMock(spec=AnyApprovalChannel)
        broken.request_approval = broken_channel
        human = MagicMock(spec=AnyApprovalChannel)
        human.request_approval = human_channel

        channel = MultiplexApprovalChannel([broken, human])
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={},
            tool_call_id="call_mux_007",
        )

        result = await channel.request_approval(context)

        assert result.approved is True
        assert result.message == "Human approved"

    @pytest.mark.asyncio
    async def test_multiplex_denies_only_when_all_channels_fail(self):
        """When every channel errors, the request resolves to a denial."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        async def broken_channel(ctx):
            raise Exception("bad token")

        broken1 = MagicMock(spec=AnyApprovalChannel)
        broken1.request_approval = broken_channel
        broken2 = MagicMock(spec=AnyApprovalChannel)
        broken2.request_approval = broken_channel

        channel = MultiplexApprovalChannel([broken1, broken2])
        context = ApprovalContext(
            tool_name="Bash",
            tool_args={},
            tool_call_id="call_mux_008",
        )

        result = await channel.request_approval(context)

        assert result.approved is False
        assert result.message == "All approval channels failed"

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

        deny_channel = MagicMock(spec=AnyApprovalChannel)

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

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        # Mock shutdown requested
        original = getattr(sys, "zrb_shutdown_requested", False)
        try:
            setattr(sys, "zrb_shutdown_requested", True)

            mock_channel = MagicMock(spec=AnyApprovalChannel)
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
            setattr(sys, "zrb_shutdown_requested", original)

    @pytest.mark.asyncio
    async def test_multiplex_notify_shutdown(self):
        """Test that notify returns early on shutdown."""
        import sys

        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        # Mock shutdown requested
        original = getattr(sys, "zrb_shutdown_requested", False)
        try:
            setattr(sys, "zrb_shutdown_requested", True)

            mock_channel = MagicMock(spec=AnyApprovalChannel)
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
            setattr(sys, "zrb_shutdown_requested", original)

    @pytest.mark.asyncio
    async def test_multiplex_notify_without_context(self, mock_channel):
        """Test that notify works without context parameter."""
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel

        channel = MultiplexApprovalChannel([mock_channel])

        await channel.notify("Test notification")

        mock_channel.notify.assert_called_once_with("Test notification", None)

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

        mock_channel = MagicMock(spec=AnyApprovalChannel)
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
        original = getattr(sys, "zrb_shutdown_requested", False)
        try:
            # Test default
            if hasattr(sys, "zrb_shutdown_requested"):
                delattr(sys, "zrb_shutdown_requested")
            assert is_shutdown_requested() is False

            # Test set to True
            setattr(sys, "zrb_shutdown_requested", True)
            assert is_shutdown_requested() is True

            # Test set to False
            setattr(sys, "zrb_shutdown_requested", False)
            assert is_shutdown_requested() is False
        finally:
            setattr(sys, "zrb_shutdown_requested", original)
