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

    @pytest.mark.asyncio
    async def test_handle_response_deny(self, channel):
        """`n` triggers the deny branch and broadcasts a [DENIED] message."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        channel.handle_response("n", "id1")
        res = await task
        assert res.approved is False
        assert "denied" in (res.message or "").lower()

    @pytest.mark.asyncio
    async def test_handle_response_unknown_treated_as_deny(self, channel):
        """Unknown responses are denied with the raw text included."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        channel.handle_response("maybe", "id1")
        res = await task
        assert res.approved is False
        assert "maybe" in (res.message or "")

    @pytest.mark.asyncio
    async def test_handle_response_non_string_type(self, channel):
        """Non-string responses are rejected with an [ERROR] broadcast."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        # bypass the public string-only contract to exercise the defensive branch
        channel.handle_response(42, "id1")
        res = await task
        assert res.approved is False
        assert "Invalid response type" in (res.message or "")

    @pytest.mark.asyncio
    async def test_handle_response_fallback_when_one_pending(self, channel):
        """When exactly one approval is pending, omitting tool_call_id still applies."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        applied = channel.handle_response("y")
        assert applied is True
        res = await task
        assert res.approved is True

    @pytest.mark.asyncio
    async def test_handle_edit_response_invalid_format(self, channel):
        """Garbage edit content denies the call with an [Invalid format] message."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)
        channel.handle_response("e", "id1")
        channel.handle_edit_response("not json nor yaml-as-dict")
        res = await task
        assert res.approved is False
        assert "Invalid" in (res.message or "")

    @pytest.mark.asyncio
    async def test_parse_edited_content_via_yaml(self, channel):
        """Edit content that is valid YAML (but not JSON) parses through the yaml path."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)
        channel.handle_response("e", "id1")
        # YAML mapping, not valid JSON
        channel.handle_edit_response("a: 1\nb: two\n")
        res = await task
        assert res.approved is True
        assert res.override_args == {"a": 1, "b": "two"}

    @pytest.mark.asyncio
    async def test_parse_edited_content_strips_code_fence(self, channel):
        """Edit content wrapped in ``` fences still parses."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("tool", {}, "id1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)
        channel.handle_response("e", "id1")
        channel.handle_edit_response('```\n{"x": 1}\n```')
        res = await task
        assert res.approved is True
        assert res.override_args == {"x": 1}

    def test_get_editing_args_returns_args_when_waiting(self, mock_session_manager):
        """get_editing_args surfaces the pending args once edit mode is active."""
        from zrb.llm.approval.approval_channel import ApprovalContext
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        ch = HTTPChatApprovalChannel(mock_session_manager, "s")
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)

            async def _drive():
                ctx = ApprovalContext("tool", {"k": "v"}, "id1")
                task = asyncio.create_task(ch.request_approval(ctx))
                await asyncio.sleep(0.01)
                ch.handle_response("e", "id1")
                assert ch.get_editing_args() == {"k": "v"}
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            loop.run_until_complete(_drive())
        finally:
            loop.close()
            asyncio.set_event_loop(None)


class TestHTTPChatApprovalChannelEditModeRecovery:
    """Cancelling an approval mid-edit must not strand the channel.

    An edit slot surviving cancellation leaves is_waiting_for_edit() true
    forever, so the next approval's answer routes to the dead tool call and is
    silently dropped.
    """

    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def channel(self, mock_session_manager):
        from zrb.runner.chat.http_chat import HTTPChatApprovalChannel

        return HTTPChatApprovalChannel(mock_session_manager, "sess1")

    async def _start_edit_mode(self, channel, tool_call_id):
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("Write", {"path": "a.txt"}, tool_call_id)
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)
        channel.handle_response("e", tool_call_id)
        assert channel.is_waiting_for_edit()
        return task

    @pytest.mark.asyncio
    async def test_cancel_during_edit_clears_edit_mode(self, channel):
        task = await self._start_edit_mode(channel, "call-1")

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert channel.is_waiting_for_edit() is False
        assert channel.debug_state()["waiting_for_edit_id"] is None

    @pytest.mark.asyncio
    async def test_next_approval_answered_after_cancel_during_edit(self, channel):
        from zrb.llm.approval.approval_channel import ApprovalContext

        cancelled = await self._start_edit_mode(channel, "call-1")
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled

        # A fresh approval must be answerable on the first try.
        ctx = ApprovalContext("Bash", {"cmd": "ls"}, "call-2")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        assert channel.handle_response("y", "call-2") is True
        result = await task
        assert result.approved is True

    @pytest.mark.asyncio
    async def test_stale_edit_slot_falls_through_to_pending_approval(self, channel):
        """A stale slot must not swallow the answer meant for a live call."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        task = await self._start_edit_mode(channel, "call-1")
        # Drop the future the way cancellation does, but leave the slot set.
        channel.handle_edit_response_obj({"path": "b.txt"})
        await task

        ctx = ApprovalContext("Bash", {"cmd": "ls"}, "call-2")
        task2 = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)
        assert channel.handle_response("y") is True
        assert (await task2).approved is True

    def test_edit_handlers_report_not_handled_when_idle(self, channel):
        assert channel.handle_edit_response("y") is False
        assert channel.handle_edit_response_obj({"a": 1}) is False

    @pytest.mark.asyncio
    async def test_edit_response_for_other_tool_call_leaves_slot_intact(self, channel):
        task = await self._start_edit_mode(channel, "call-1")

        # Edit mode is a single slot; a response aimed elsewhere is not an edit.
        assert channel.handle_edit_response('{"a": 1}', "other-call") is False
        assert channel.is_waiting_for_edit() is True

        assert channel.handle_edit_response('{"a": 1}', "call-1") is True
        assert (await task).override_args == {"a": 1}

    @pytest.mark.asyncio
    async def test_broadcast_tasks_are_retained_until_complete(self, channel):
        """Broadcasts must hold a strong ref so the loop cannot GC them."""
        from zrb.llm.approval.approval_channel import ApprovalContext

        ctx = ApprovalContext("Bash", {"cmd": "ls"}, "call-1")
        task = asyncio.create_task(channel.request_approval(ctx))
        await asyncio.sleep(0.01)

        channel.handle_response("y", "call-1")
        assert await task is not None
        await asyncio.sleep(0.01)
        # Broadcast completed and deregistered itself.
        assert channel.debug_state()["broadcast_task_count"] == 0
