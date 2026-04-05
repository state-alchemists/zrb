"""Tests for hook result processing in run_agent.

These tests verify that hook results (systemMessage, additionalContext)
are properly extracted and processed by run_agent.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run_agent import (
    _extract_additional_context,
    _extract_system_message,
)
from zrb.llm.hook.executor import HookExecutionResult
from zrb.llm.hook.types import HookEvent


class TestExtractSystemMessage:
    """Tests for _extract_system_message helper."""

    def test_returns_none_for_empty_results(self):
        """Empty results list should return None."""
        result = _extract_system_message([])
        assert result is None

    def test_returns_none_when_no_system_message(self):
        """Results without system_message should return None."""
        results = [
            HookExecutionResult(success=True, message="test"),
            HookExecutionResult(success=True, data={"foo": "bar"}),
        ]
        assert _extract_system_message(results) is None

    def test_returns_first_system_message(self):
        """Should return the first system_message found."""
        results = [
            HookExecutionResult(success=True, system_message="first"),
            HookExecutionResult(success=True, system_message="second"),
        ]
        assert _extract_system_message(results) == "first"

    def test_finds_system_message_in_middle(self):
        """Should find system_message even if not in first result."""
        results = [
            HookExecutionResult(success=True, message="other"),
            HookExecutionResult(success=True, system_message="found it"),
            HookExecutionResult(success=True, message="last"),
        ]
        assert _extract_system_message(results) == "found it"


class TestExtractAdditionalContext:
    """Tests for _extract_additional_context helper."""

    def test_returns_none_for_empty_results(self):
        """Empty results list should return None."""
        result = _extract_additional_context([])
        assert result is None

    def test_returns_none_when_no_additional_context(self):
        """Results without additional_context should return None."""
        results = [
            HookExecutionResult(success=True, message="test"),
            HookExecutionResult(success=True, data={"foo": "bar"}),
        ]
        assert _extract_additional_context(results) is None

    def test_returns_first_additional_context(self):
        """Should return the first additional_context found."""
        results = [
            HookExecutionResult(success=True, additional_context="first"),
            HookExecutionResult(success=True, additional_context="second"),
        ]
        assert _extract_additional_context(results) == "first"

    def test_finds_additional_context_in_middle(self):
        """Should find additional_context even if not in first result."""
        results = [
            HookExecutionResult(success=True, message="other"),
            HookExecutionResult(success=True, additional_context="found it"),
            HookExecutionResult(success=True, message="last"),
        ]
        assert _extract_additional_context(results) == "found it"


class TestHookResultProcessing:
    """Tests for hook result processing in run_agent flow."""

    @pytest.mark.asyncio
    async def test_session_end_with_system_message_continues_session(self):
        """Verify that SESSION_END hook returning systemMessage continues the session.

        This is the critical path for journaling:
        1. Hook returns systemMessage at SESSION_END
        2. run_agent sees it and continues with that message
        3. LLM responds, then SESSION_END fires again
        4. Hook returns nothing (preventing infinite loop)
        """
        from zrb.llm.hook.interface import HookResult
        from zrb.llm.hook.manager import HookManager

        # Track hook call count
        call_count = 0

        async def tracking_hook(context):
            nonlocal call_count
            call_count += 1

            # First SESSION_END call returns systemMessage
            if context.event == HookEvent.SESSION_END and call_count == 1:
                return HookResult.with_system_message("Test reminder message")
            # Subsequent calls return nothing
            return HookResult()

        manager = HookManager()
        manager.register(
            tracking_hook,
            events=[
                HookEvent.SESSION_START,
                HookEvent.SESSION_END,
            ],
        )

        # Execute hooks and check results
        results = await manager.execute_hooks(
            HookEvent.SESSION_END, {"output": "test output", "history": []}
        )

        # Verify systemMessage was extracted
        system_msg = _extract_system_message(results)
        assert system_msg == "Test reminder message"

    @pytest.mark.asyncio
    async def test_session_start_additional_context(self):
        """Verify that SESSION_START hook returning additionalContext is processed."""
        from zrb.llm.hook.interface import HookResult
        from zrb.llm.hook.manager import HookManager

        async def context_hook(context):
            return HookResult.with_additional_context("Injected context")

        manager = HookManager()
        manager.register(context_hook, events=[HookEvent.SESSION_START])

        results = await manager.execute_hooks(
            HookEvent.SESSION_START, {"message": "test", "history": []}
        )

        additional_ctx = _extract_additional_context(results)
        assert additional_ctx == "Injected context"

    @pytest.mark.asyncio
    async def test_user_prompt_submit_additional_context(self):
        """Verify that USER_PROMPT_SUBMIT hook returning additionalContext is processed."""
        from zrb.llm.hook.interface import HookResult
        from zrb.llm.hook.manager import HookManager

        async def context_hook(context):
            return HookResult.with_additional_context("Extra context for prompt")

        manager = HookManager()
        manager.register(context_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

        results = await manager.execute_hooks(
            HookEvent.USER_PROMPT_SUBMIT,
            {"original_message": "test", "expanded_message": "test"},
        )

        additional_ctx = _extract_additional_context(results)
        assert additional_ctx == "Extra context for prompt"


class TestJournalingHookAntiRecursion:
    """Tests for JournalingHookHandler anti-recursion protection."""

    @pytest.mark.asyncio
    async def test_journaling_hook_only_fires_once(self):
        """Verify journaling hook only sends reminder once per session."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()
        handler._session_had_significant_activity = True

        context = HookContext(event=HookEvent.SESSION_END, event_data={})

        # First SESSION_END call should return systemMessage
        result1 = await handler.handle_event(context)
        assert result1.modifications is not None
        assert "systemMessage" in result1.modifications

        # Second SESSION_END call should return nothing (already fired)
        result2 = await handler.handle_event(context)
        assert (
            result2.modifications is None
            or "systemMessage" not in result2.modifications
        )

    @pytest.mark.asyncio
    async def test_journaling_hook_requires_activity(self):
        """Verify journaling hook only fires when there was activity."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()
        # No activity flag set - should NOT fire

        context = HookContext(event=HookEvent.SESSION_END, event_data={})
        result = await handler.handle_event(context)

        assert (
            result.modifications is None or "systemMessage" not in result.modifications
        )

    @pytest.mark.asyncio
    async def test_journaling_hook_resets_on_new_session(self):
        """Verify journaling hook resets state on new session."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()
        handler._session_had_significant_activity = True
        handler._session_end_fired = True

        # Simulate new session - SESSION_START resets state
        handler.reset()  # reset() is called at SESSION_START

        # After reset, hook should fire again if there's activity
        handler._session_had_significant_activity = True

        context = HookContext(event=HookEvent.SESSION_END, event_data={})
        result = await handler.handle_event(context)

        # Should fire now because flags were reset
        assert result.modifications is not None
        assert "systemMessage" in result.modifications
