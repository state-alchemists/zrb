import asyncio
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
    text = "A" * 30
    truncated = limiter.truncate_text(text, 5)
    assert len(truncated) <= 20


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
