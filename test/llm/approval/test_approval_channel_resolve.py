"""Tests for the approval channel system."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.approval import AnyApprovalChannel


class TestResolveApprovalChannel:
    """Tests for the `resolve_approval_channel` helper."""

    def test_no_channels_returns_none(self):
        from zrb.llm.approval.multiplex_approval_channel import (
            resolve_approval_channel,
        )

        assert resolve_approval_channel([]) is None

    def test_single_channel_returned_unwrapped(self):
        from zrb.llm.approval.multiplex_approval_channel import (
            resolve_approval_channel,
        )

        channel = MagicMock(spec=AnyApprovalChannel)
        assert resolve_approval_channel([channel]) is channel

    @pytest.mark.asyncio
    async def test_multiple_channels_wrapped_in_multiplex(self):
        from zrb.llm.approval.multiplex_approval_channel import (
            MultiplexApprovalChannel,
            resolve_approval_channel,
        )

        channel_a = MagicMock(spec=AnyApprovalChannel)
        channel_a.notify = AsyncMock(return_value=None)
        channel_b = MagicMock(spec=AnyApprovalChannel)
        channel_b.notify = AsyncMock(return_value=None)
        result = resolve_approval_channel([channel_a, channel_b])

        assert isinstance(result, MultiplexApprovalChannel)
        await result.notify("hello")
        channel_a.notify.assert_called_once_with("hello", None)
        channel_b.notify.assert_called_once_with("hello", None)
