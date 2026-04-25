"""Tests for hook result processing in run_agent.

These tests verify that hook results (systemMessage, additionalContext)
are properly extracted and processed by run_agent.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.runner import (
    extract_additional_context,
    extract_system_message,
)
from zrb.llm.hook.executor import HookExecutionResult
from zrb.llm.hook.types import HookEvent


class TestExtractSystemMessage:
    """Tests for _extract_system_message helper."""

    def test_returns_none_for_empty_results(self):
        """Empty results list should return None."""
        result = extract_system_message([])
        assert result is None

    def test_returns_none_when_no_system_message(self):
        """Results without system_message should return None."""
        results = [
            HookExecutionResult(success=True, message="test"),
            HookExecutionResult(success=True, data={"foo": "bar"}),
        ]
        assert extract_system_message(results) is None

    def test_returns_first_system_message(self):
        """Should return the first system_message found."""
        results = [
            HookExecutionResult(success=True, system_message="first"),
            HookExecutionResult(success=True, system_message="second"),
        ]
        assert extract_system_message(results) == "first"

    def test_finds_system_message_in_middle(self):
        """Should find system_message even if not in first result."""
        results = [
            HookExecutionResult(success=True, message="other"),
            HookExecutionResult(success=True, system_message="found it"),
            HookExecutionResult(success=True, message="last"),
        ]
        assert extract_system_message(results) == "found it"


class TestExtractAdditionalContext:
    """Tests for _extract_additional_context helper."""

    def test_returns_none_for_empty_results(self):
        """Empty results list should return None."""
        result = extract_additional_context([])
        assert result is None

    def test_returns_none_when_no_additional_context(self):
        """Results without additional_context should return None."""
        results = [
            HookExecutionResult(success=True, message="test"),
            HookExecutionResult(success=True, data={"foo": "bar"}),
        ]
        assert extract_additional_context(results) is None

    def test_returns_first_additional_context(self):
        """Should return the first additional_context found."""
        results = [
            HookExecutionResult(success=True, additional_context="first"),
            HookExecutionResult(success=True, additional_context="second"),
        ]
        assert extract_additional_context(results) == "first"

    def test_finds_additional_context_in_middle(self):
        """Should find additional_context even if not in first result."""
        results = [
            HookExecutionResult(success=True, message="other"),
            HookExecutionResult(success=True, additional_context="found it"),
            HookExecutionResult(success=True, message="last"),
        ]
        assert extract_additional_context(results) == "found it"


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
        system_msg = extract_system_message(results)
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

        additional_ctx = extract_additional_context(results)
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

        additional_ctx = extract_additional_context(results)
        assert additional_ctx == "Extra context for prompt"


class TestJournalingHookAntiRecursion:
    """Tests for JournalingHookHandler anti-recursion protection."""

    @pytest.mark.asyncio
    async def test_journaling_hook_only_fires_once(self):
        """Verify journaling hook only sends reminder once per session."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()

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
    async def test_journaling_hook_fires_at_session_end(self):
        """Verify journaling hook fires at SESSION_END."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()

        context = HookContext(event=HookEvent.SESSION_END, event_data={})
        result = await handler.handle_event(context)

        # Hook should always fire at SESSION_END (LLM decides if anything is worth noting)
        assert result.modifications is not None
        assert "systemMessage" in result.modifications

    @pytest.mark.asyncio
    async def test_journaling_hook_resets_on_new_session(self):
        """Verify journaling hook resets state on new session."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()

        context_end = HookContext(event=HookEvent.SESSION_END, event_data={})

        # Fire once - sets the anti-recursion flag
        result1 = await handler.handle_event(context_end)
        assert result1.modifications is not None
        assert "systemMessage" in result1.modifications

        # Second call should NOT fire (anti-recursion)
        result2 = await handler.handle_event(context_end)
        assert (
            result2.modifications is None
            or "systemMessage" not in result2.modifications
        )

        # Simulate new session - SESSION_START resets state
        handler.reset()

        # After reset, hook should fire again
        result3 = await handler.handle_event(context_end)
        assert result3.modifications is not None
        assert "systemMessage" in result3.modifications

    @pytest.mark.asyncio
    async def test_journaling_hook_disabled_returns_empty(self):
        """Verify journaling hook returns empty when disabled."""
        from unittest.mock import patch

        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        with patch("zrb.llm.hook.journal.CFG") as mock_cfg:
            mock_cfg.LLM_INCLUDE_JOURNAL = False
            mock_cfg.LLM_INCLUDE_JOURNAL_REMINDER = False
            handler = JournalingHookHandler()
            context = HookContext(event=HookEvent.SESSION_END, event_data={})
            result = await handler.handle_event(context)

        assert result.modifications is None or "systemMessage" not in (
            result.modifications or {}
        )

    @pytest.mark.asyncio
    async def test_journaling_hook_session_start_resets_via_event(self):
        """Verify SESSION_START event triggers reset through handle_event."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()

        # Fire SESSION_END first
        end_ctx = HookContext(event=HookEvent.SESSION_END, event_data={})
        result1 = await handler.handle_event(end_ctx)
        assert result1.modifications is not None
        assert "systemMessage" in result1.modifications

        # Firing SESSION_END again should NOT fire (anti-recursion)
        result2 = await handler.handle_event(end_ctx)
        assert result2.modifications is None or "systemMessage" not in (
            result2.modifications or {}
        )

        # SESSION_START event should reset state
        start_ctx = HookContext(event=HookEvent.SESSION_START, event_data={})
        await handler.handle_event(start_ctx)

        # Now SESSION_END should fire again
        result3 = await handler.handle_event(end_ctx)
        assert result3.modifications is not None
        assert "systemMessage" in result3.modifications

    @pytest.mark.asyncio
    async def test_journaling_hook_non_session_event_returns_empty(self):
        """Verify non-session events return empty result."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import JournalingHookHandler

        handler = JournalingHookHandler()
        context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})
        result = await handler.handle_event(context)

        assert result.modifications is None or "systemMessage" not in (
            result.modifications or {}
        )

    @pytest.mark.asyncio
    async def test_create_journaling_hook_factory_function(self):
        """Verify create_journaling_hook() returns a callable hook."""
        from zrb.llm.hook.interface import HookContext
        from zrb.llm.hook.journal import create_journaling_hook

        hook = create_journaling_hook()
        assert callable(hook)

        # The returned callable should work as a hook
        context = HookContext(event=HookEvent.SESSION_END, event_data={})
        result = await hook(context)
        assert result.modifications is not None
        assert "systemMessage" in result.modifications

    @pytest.mark.asyncio
    async def test_create_journaling_hook_factory_with_manager_enabled(self):
        """Verify create_journaling_hook_factory registers hooks when enabled."""
        from unittest.mock import MagicMock, patch

        from zrb.llm.hook.journal import create_journaling_hook_factory
        from zrb.llm.hook.manager import HookManager

        with patch("zrb.llm.hook.journal.CFG") as mock_cfg, patch(
            "zrb.llm.hook.manager.manager.CFG"
        ) as mock_mgr_cfg:
            mock_cfg.LLM_INCLUDE_JOURNAL = True
            mock_cfg.LLM_INCLUDE_JOURNAL_REMINDER = True
            mock_mgr_cfg.LLM_INCLUDE_JOURNAL = False
            mock_mgr_cfg.ROOT_GROUP_NAME = "zrb"
            mock_mgr_cfg.LLM_PLUGIN_DIRS = []
            mock_mgr_cfg.HOOKS_DIRS = []
            mock_mgr_cfg.LLM_JOURNAL_DIR = "/tmp/test"
            mock_mgr_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"

            factory = create_journaling_hook_factory()
            manager = HookManager()
            factory(manager)

            # Hook should be registered for SESSION_END
            results = await manager.execute_hooks(HookEvent.SESSION_END, {})
            system_msg = extract_system_message(results)
            assert system_msg is not None

    @pytest.mark.asyncio
    async def test_create_journaling_hook_factory_with_manager_disabled(self):
        """Verify create_journaling_hook_factory skips registration when disabled."""
        from unittest.mock import patch

        from zrb.llm.hook.journal import create_journaling_hook_factory
        from zrb.llm.hook.manager import HookManager

        with patch("zrb.llm.hook.journal.CFG") as mock_cfg, patch(
            "zrb.llm.hook.manager.manager.CFG"
        ) as mock_mgr_cfg:
            mock_cfg.LLM_INCLUDE_JOURNAL = False
            mock_cfg.LLM_INCLUDE_JOURNAL_REMINDER = False
            mock_mgr_cfg.LLM_INCLUDE_JOURNAL = False
            mock_mgr_cfg.ROOT_GROUP_NAME = "zrb"
            mock_mgr_cfg.LLM_PLUGIN_DIRS = []
            mock_mgr_cfg.HOOKS_DIRS = []
            mock_mgr_cfg.LLM_JOURNAL_DIR = "/tmp/test"
            mock_mgr_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"

            factory = create_journaling_hook_factory()
            manager = HookManager()
            factory(manager)

            # No hooks should be registered
            results = await manager.execute_hooks(HookEvent.SESSION_END, {})
            system_msg = extract_system_message(results)
            assert system_msg is None
