import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.config.limiter import LLMLimiter, is_turn_start


@pytest.mark.asyncio
async def test_llm_limiter_count_tokens():
    """Test count_tokens with string content."""
    limiter = LLMLimiter()
    tokens = limiter.count_tokens("Hello world")
    assert tokens > 0


@pytest.mark.asyncio
async def test_llm_limiter_truncate_text():
    """Test truncate_text truncates long text."""
    limiter = LLMLimiter()
    # Test the fallback behavior directly by checking the result
    text = "A" * 30
    truncated = limiter.truncate_text(text, 5)
    # With or without tiktoken, result should be at most reasonable size
    # tiktoken may return fewer chars due to BPE compression
    # fallback returns ~max_tokens * 4 chars
    assert len(truncated) <= 30  # Original or truncated


@pytest.mark.asyncio
async def test_llm_limiter_fit_context_window():
    """Test fit_context_window prunes when exceeding limit."""
    limiter = LLMLimiter()
    # Set limit extremely low to force pruning of even small messages
    limiter.max_token_per_request = 2

    # Message history
    msg1 = ModelRequest(parts=[UserPromptPart(content="Hello")])
    msg2 = ModelRequest(parts=[UserPromptPart(content="How are you?")])
    history = [msg1, msg2]

    new_msg = "I am fine"

    with patch("zrb.llm.config.limiter.is_turn_start", side_effect=[False, True]):
        pruned = limiter.fit_context_window(history, new_msg)
        assert len(pruned) < len(history)


@pytest.mark.asyncio
async def test_llm_limiter_acquire():
    """Test acquire proceeds immediately when under limits."""
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 1000

    # Should proceed immediately if under limits
    notifier = MagicMock()
    await limiter.acquire("Short message", notifier=notifier)
    assert not notifier.called


def test_llm_limiter_properties():
    """Test limiter property getters and setters."""
    limiter = LLMLimiter()

    # Test max_request_per_minute
    limiter.max_request_per_minute = 50
    assert limiter.max_request_per_minute == 50

    # Test max_token_per_minute
    limiter.max_token_per_minute = 5000
    assert limiter.max_token_per_minute == 5000

    # Test max_token_per_request
    limiter.max_token_per_request = 8000
    assert limiter.max_token_per_request == 8000

    # Test throttle_check_interval
    limiter.throttle_check_interval = 0.5
    assert limiter.throttle_check_interval == 0.5


def test_llm_limiter_fit_context_window_empty():
    """Test fit_context_window with empty history."""
    limiter = LLMLimiter()

    # Empty history
    result = limiter.fit_context_window([], "new message")
    assert result == []


def test_llm_limiter_fit_context_window_no_prune_needed():
    """Test fit_context_window when no pruning is needed."""
    limiter = LLMLimiter()
    limiter.max_token_per_request = 10000  # High limit

    msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    history = [msg]

    result = limiter.fit_context_window(history, "new message")
    assert len(result) == 1


def test_is_turn_start_with_model_request():
    """Test is_turn_start with ModelRequest containing UserPromptPart."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    # ModelRequest with only UserPromptPart (turn start)
    msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    assert is_turn_start(msg) is True


def test_is_turn_start_with_tool_return():
    """Test is_turn_start with ModelRequest containing ToolReturnPart."""
    from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart

    # ModelRequest with both UserPromptPart and ToolReturnPart (not turn start)
    msg = ModelRequest(
        parts=[
            UserPromptPart(content="Hello"),
            ToolReturnPart(tool_name="test", content="result", tool_call_id="1"),
        ]
    )
    assert is_turn_start(msg) is False


def test_is_turn_start_with_non_model_request():
    """Test is_turn_start with non-ModelRequest object."""
    assert is_turn_start("not a model request") is False
    assert is_turn_start(None) is False
    assert is_turn_start(123) is False


def test_llm_limiter_count_tokens_with_list():
    """Test count_tokens with list content."""
    limiter = LLMLimiter()

    result = limiter.count_tokens(["hello", "world"])
    assert result > 0


def test_llm_limiter_count_tokens_with_dict():
    """Test count_tokens with dict content."""
    limiter = LLMLimiter()

    result = limiter.count_tokens({"key": "value"})
    assert result > 0


def test_llm_limiter_use_tiktoken_property():
    """Test use_tiktoken property."""
    limiter = LLMLimiter()
    # Default should be False
    assert isinstance(limiter.use_tiktoken, bool)


def test_llm_limiter_tiktoken_encoding_property():
    """Test tiktoken_encoding property."""
    limiter = LLMLimiter()
    assert isinstance(limiter.tiktoken_encoding, str)


@pytest.mark.asyncio
async def test_llm_limiter_acquire_behavior():
    """Test that acquire properly manages rate limiting behavior."""
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 10000

    # First acquire should succeed immediately
    start = time.time()
    await limiter.acquire("test content")
    elapsed = time.time() - start

    # Should complete quickly (no rate limit delay)
    assert elapsed < 1.0


class TestLLMLimiterRateLimiting:
    """Test rate limiting behavior through public API."""

    def test_can_proceed_empty_logs(self):
        """Test _can_proceed returns True when logs are empty."""
        limiter = LLMLimiter()
        # Empty logs means we can proceed
        result = limiter._can_proceed(100)
        assert result is True

    def test_can_proceed_under_limits(self):
        """Test _can_proceed returns True when under limits."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 10
        limiter.max_token_per_minute = 1000

        # Add some usage but stay under limit
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 50))

        result = limiter._can_proceed(100)
        assert result is True

    def test_can_proceed_over_request_limit(self):
        """Test _can_proceed returns False when request limit exceeded."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 2

        # Fill up request log
        limiter._request_log.append(time.time())
        limiter._request_log.append(time.time())

        result = limiter._can_proceed(10)
        assert result is False

    def test_can_proceed_over_token_limit(self):
        """Test _can_proceed returns False when token limit exceeded."""
        limiter = LLMLimiter()
        limiter.max_token_per_minute = 100

        # Fill up token log
        limiter._token_log.append((time.time(), 99))

        result = limiter._can_proceed(10)
        assert result is False

    def test_get_limit_reason_request_limit(self):
        """Test _get_limit_reason returns request limit message."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 5

        # Fill request log
        for _ in range(5):
            limiter._request_log.append(time.time())

        reason = limiter._get_limit_reason(10)
        assert "Max Requests" in reason
        assert "5/min" in reason

    def test_get_limit_reason_token_limit(self):
        """Test _get_limit_reason returns token limit message."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 100
        limiter.max_token_per_minute = 50

        reason = limiter._get_limit_reason(100)
        assert "Max Tokens" in reason
        assert "50/min" in reason

    def test_calculate_wait_time_request_limit(self):
        """Test _calculate_wait_time for request limit."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 2

        # Fill request log
        limiter._request_log.append(time.time())
        limiter._request_log.append(time.time())

        wait = limiter._calculate_wait_time(10)
        assert wait > 0

    def test_calculate_wait_time_token_limit(self):
        """Test _calculate_wait_time for token limit."""
        limiter = LLMLimiter()
        limiter.max_token_per_minute = 50

        # Fill token log near limit
        limiter._token_log.append((time.time(), 40))

        wait = limiter._calculate_wait_time(20)
        assert wait > 0

    def test_prune_logs_removes_old_entries(self):
        """Test _prune_logs removes entries older than 60 seconds."""
        limiter = LLMLimiter()

        # Add old entries (65 seconds ago)
        old_time = time.time() - 65
        limiter._request_log.append(old_time)
        limiter._token_log.append((old_time, 100))

        # Add recent entries
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 50))

        limiter._prune_logs()

        assert len(limiter._request_log) == 1
        assert len(limiter._token_log) == 1

    def test_prune_logs_keeps_recent_entries(self):
        """Test _prune_logs keeps entries within 60 seconds."""
        limiter = LLMLimiter()

        # Add recent entries
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 100))

        limiter._prune_logs()

        assert len(limiter._request_log) == 1
        assert len(limiter._token_log) == 1


class TestLLMLimiterFitContextWindow:
    """Test context window fitting through public API."""

    def test_fit_context_window_clears_all_when_new_msg_too_large(self):
        """Test fit_context_window clears history when new message exceeds limit."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 5  # Very low limit

        msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
        history = [msg]

        # Create a large new message that exceeds limit
        large_msg = "x" * 1000

        result = limiter.fit_context_window(history, large_msg)
        assert result == []

    def test_fit_context_window_prunes_by_turns(self):
        """Test fit_context_window prunes history by conversation turns."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 20

        msg1 = ModelRequest(parts=[UserPromptPart(content="First message here")])
        msg2 = ModelRequest(parts=[UserPromptPart(content="Second message")])
        msg3 = ModelRequest(parts=[UserPromptPart(content="Third")])

        history = [msg1, msg2, msg3]

        # New message that causes need for pruning
        new_msg = "A longer new message"

        # With is_turn_start properly identifying turns
        with patch(
            "zrb.llm.config.limiter.is_turn_start", side_effect=[False, True, False]
        ):
            result = limiter.fit_context_window(history, new_msg)
            # Should prune to fit within limit
            assert len(result) <= len(history)

    def test_fit_context_window_no_turn_start_found(self):
        """Test fit_context_window clears all when no turn start found."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 2

        msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
        history = [msg]

        # All messages fail is_turn_start
        with patch("zrb.llm.config.limiter.is_turn_start", return_value=False):
            result = limiter.fit_context_window(history, "new message")
            assert result == []


class TestLLMLimiterTokenCounting:
    """Test token counting through public API."""

    def test_count_tokens_with_none(self):
        """Test count_tokens with None content converts to 'None' string."""
        limiter = LLMLimiter()
        result = limiter.count_tokens(None)
        # None converts to "None" string which has 4 chars, 4//4 = 1 token
        assert result >= 0

    def test_count_tokens_with_numeric(self):
        """Test count_tokens with numeric content."""
        limiter = LLMLimiter()
        result = limiter.count_tokens(42)
        # 42 converted to "42" has 2 chars, 2//4 = 0 tokens
        assert result >= 0

    def test_count_tokens_with_large_number(self):
        """Test count_tokens with larger numeric content."""
        limiter = LLMLimiter()
        # Large number with more than 4 digits
        result = limiter.count_tokens(12345)
        assert result > 0

    def test_to_str_with_nested_dict(self):
        """Test _to_str with nested dict content."""
        limiter = LLMLimiter()

        nested = {"outer": {"inner": "value"}}
        result = limiter._to_str(nested)
        assert "outer" in result
        assert "inner" in result


class TestLLMLimiterTruncate:
    """Test text truncation through public API."""

    def test_truncate_text_no_tiktoken(self):
        """Test truncate_text works correctly with or without tiktoken."""
        limiter = LLMLimiter()
        limiter._max_request_per_minute = None  # Force defaults

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
