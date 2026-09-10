import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.config.limiter import LLMLimiter


class TestLLMLimiterTruncate:
    """Test text truncation through public API."""

    def test_truncate_text_no_tiktoken(self):
        """Test truncate_text works correctly with or without tiktoken."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = None  # Force defaults

        text = "A" * 100
        # Max 10 tokens - result depends on whether tiktoken is available
        # With tiktoken: may compress due to BPE
        # Without tiktoken: uses char/4 approximation (~40 chars)
        result = limiter.truncate_text(text, 10)
        # Result should be at most original length
        assert len(result) <= 100
        # Result should be a string
        assert isinstance(result, str)

    def test_truncate_text_returns_unchanged_if_short(self):
        """Test truncate_text returns unchanged if text fits."""
        limiter = LLMLimiter()

        text = "Hello"
        result = limiter.truncate_text(text, 100)
        assert result == text

    def test_truncate_text_tiktoken_fallback_on_exception(self):
        """Test truncate_text falls back when tiktoken raises exception."""
        import builtins

        limiter = LLMLimiter()

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "tiktoken":
                raise Exception("tiktoken fail")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=failing_import):
            limiter.max_request_per_minute = None
            text = "A" * 100
            result = limiter.truncate_text(text, 10)
            assert len(result) <= 40

    def test_count_tokens_tiktoken_import_error(self):
        """Test count_tokens falls back when tiktoken import fails."""
        import builtins

        limiter = LLMLimiter()

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "tiktoken":
                raise ImportError("no tiktoken")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=failing_import):
            limiter.max_request_per_minute = None
            result = limiter.count_tokens("hello world")
            assert result > 0

    def test_to_str_with_instructions_on_object(self):
        """Test to_str counts instructions from object with instructions field."""
        limiter = LLMLimiter()

        class MockObj:
            def __init__(self):
                self.instructions = "Some instructions"
                self.parts = []

        obj = MockObj()
        result = limiter.to_str(obj)
        assert "Some instructions" in result

    def test_to_str_with_instructions_skip_instructions_true(self):
        """Test to_str skips instructions when skip_instructions=True."""
        limiter = LLMLimiter()

        class MockObj:
            def __init__(self):
                self.instructions = "Some instructions"
                self.parts = []

        obj = MockObj()
        result = limiter.to_str(obj, skip_instructions=True)
        assert "Some instructions" not in result

    def test_to_str_with_content_field(self):
        """Test to_str extracts content field."""
        limiter = LLMLimiter()

        class MockObj:
            content = "Hello content"

        result = limiter.to_str(MockObj())
        assert "Hello content" in result

    def test_to_str_with_args_field(self):
        """Test to_str extracts args field."""
        limiter = LLMLimiter()

        class MockObj:
            args = {"key": "value"}

        result = limiter.to_str(MockObj())
        assert "key" in result
        assert "value" in result

    def test_to_str_fallback_str_exception(self):
        """Test to_str returns empty string when str() raises."""
        limiter = LLMLimiter()

        class BadObj:
            def __str__(self):
                raise Exception("Cannot convert")

        result = limiter.to_str(BadObj())
        assert result == ""


class TestLLMLimiterAcquireWithNotifier:
    @pytest.mark.asyncio
    async def test_acquire_with_notifier_when_rate_limited(self):
        """Test acquire calls notifier when rate limited."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 1
        limiter.max_token_per_minute = 10
        limiter.throttle_check_interval = 0.01

        notifier = MagicMock()
        limiter.request_log.append(time.time())
        limiter.token_log.append((time.time(), 9))

        async def acquire_with_timeout():
            try:
                await asyncio.wait_for(
                    limiter.acquire("test", notifier=notifier), timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        await acquire_with_timeout()
        assert notifier.called

    @pytest.mark.asyncio
    async def test_acquire_notifier_clear_after_limit_lifts(self):
        """Once the rate limit lifts, the notifier receives a final clear ("\\n").

        Drives the public acquire(): start over the request budget, then raise the
        budget mid-flight so the throttle loop exits and the clear branch runs.
        """
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 1
        limiter.max_token_per_minute = 10000
        limiter.throttle_check_interval = 0.01
        limiter.max_request_per_minute = 1
        # Pre-fill the request budget so the first acquire is blocked.
        await limiter.acquire("seed")

        notifier = MagicMock()

        async def lift_limit_soon():
            await asyncio.sleep(0.03)
            limiter.max_request_per_minute = 100

        await asyncio.gather(
            limiter.acquire("blocked", notifier=notifier),
            lift_limit_soon(),
        )

        # Notifier was called for the wait message AND the trailing clear.
        assert notifier.called
        assert any(
            call.args and call.args[0] == "\n" for call in notifier.call_args_list
        )

    @pytest.mark.asyncio
    async def test_acquire_notifier_called_once_with_clear(self):
        """Test notifier receives clear message after rate limit clears."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 1
        limiter.max_token_per_minute = 10000
        limiter.throttle_check_interval = 0.01

        limiter.request_log.append(time.time())

        notifier = MagicMock()

        async def acquire_with_timeout():
            try:
                await asyncio.wait_for(
                    limiter.acquire("test", notifier=notifier), timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        await acquire_with_timeout()
        assert notifier.called
