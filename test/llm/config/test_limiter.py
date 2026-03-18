import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.config.limiter import LLMLimiter, is_turn_start


@pytest.mark.asyncio
async def test_llm_limiter_count_tokens():
    limiter = LLMLimiter()
    tokens = limiter.count_tokens("Hello world")
    assert tokens > 0


@pytest.mark.asyncio
async def test_llm_limiter_truncate_text():
    limiter = LLMLimiter()
    text = "A" * 30
    truncated = limiter.truncate_text(text, 5)
    assert len(truncated) <= 20


@pytest.mark.asyncio
async def test_llm_limiter_fit_context_window():
    limiter = LLMLimiter()
    # Set limit extremely low to force pruning of even small messages
    limiter.max_token_per_request = 2

    # Message history
    msg1 = ModelRequest(parts=[UserPromptPart(content="Hello")])
    msg2 = ModelRequest(parts=[UserPromptPart(content="How are you?")])
    history = [msg1, msg2]

    new_msg = "I am fine"

    # Pruning logic in fit_context_window uses _count_tokens
    # which for non-tiktoken is len(text) // 4.
    # msg1 tokens = 5 // 4 = 1
    # msg2 tokens = 12 // 4 = 3
    # new_msg tokens = 9 // 4 = 2
    # Total = 1 + 3 + 2 = 6. Limit = 2 * 0.95 = 1.9.
    # It must prune.

    with patch("zrb.llm.config.limiter.is_turn_start", side_effect=[False, True]):
        pruned = limiter.fit_context_window(history, new_msg)
        assert len(pruned) < len(history)


@pytest.mark.asyncio
async def test_llm_limiter_acquire():
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 1000

    # Should proceed immediately if under limits
    notifier = MagicMock()
    await limiter.acquire("Short message", notifier=notifier)
    assert not notifier.called


# New tests for improved coverage


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


def test_llm_limiter_prune_logs():
    """Test _prune_logs removes old entries."""
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 1000

    # Add some old entries
    old_time = time.time() - 120  # 2 minutes ago
    limiter._request_log.append(old_time)
    limiter._token_log.append((old_time, 100))

    # Add current entry
    limiter._request_log.append(time.time())
    limiter._token_log.append((time.time(), 200))

    limiter._prune_logs()

    # Old entries should be removed
    assert len(limiter._request_log) == 1
    assert len(limiter._token_log) == 1


def test_llm_limiter_can_proceed():
    """Test _can_proceed method."""
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 10
    limiter.max_token_per_minute = 100

    # Empty logs should allow proceeding
    assert limiter._can_proceed(50) is True

    # Add request near limit
    import time

    limiter._request_log.extend([time.time()] * 9)

    # Should still be able to proceed (9 < 10)
    assert limiter._can_proceed(10) is True

    # Add one more request
    limiter._request_log.append(time.time())

    # Now should not proceed (10 >= 10)
    assert limiter._can_proceed(10) is False


def test_llm_limiter_get_limit_reason():
    """Test _get_limit_reason returns appropriate message."""
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 5
    limiter.max_token_per_minute = 100

    # Token limit
    reason = limiter._get_limit_reason(100)
    assert "Max Tokens" in reason

    # Fill request log to trigger request limit
    for _ in range(5):
        limiter._request_log.append(time.time())

    reason = limiter._get_limit_reason(10)
    assert "Max Requests" in reason


def test_llm_limiter_calculate_wait_time():
    """Test _calculate_wait_time method."""
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 5
    limiter.max_token_per_minute = 100

    # No limits hit, default wait
    wait = limiter._calculate_wait_time(10)
    assert wait == 1.0

    # Add requests at the limit
    now = time.time()
    for _ in range(5):
        limiter._request_log.append(now)

    wait = limiter._calculate_wait_time(10)
    assert wait > 0


def test_llm_limiter_to_str():
    """Test _to_str method for various types."""
    limiter = LLMLimiter()

    # String
    assert limiter._to_str("hello") == "hello"

    # Int
    assert limiter._to_str(42) == "42"

    # Float
    assert limiter._to_str(3.14) == "3.14"

    # Bool
    assert limiter._to_str(True) == "True"

    # None
    assert limiter._to_str(None) == "None"

    # List
    assert limiter._to_str(["a", "b"]) == "ab"

    # Dict
    result = limiter._to_str({"key": "value"})
    assert "key" in result
    assert "value" in result


def test_llm_limiter_to_str_with_object():
    """Test _to_str with object having parts and content attributes."""
    limiter = LLMLimiter()

    mock_obj = MagicMock()
    mock_obj.parts = []
    mock_obj.instructions = "Do this"
    mock_obj.content = "content text"
    mock_obj.args = {"arg1": "value1"}

    result = limiter._to_str(mock_obj)
    assert "Do this" in result
    assert "content text" in result


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


def test_llm_limiter_acquire_records_usage():
    """Test that acquire properly records usage."""
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 10000

    initial_requests = len(limiter._request_log)
    initial_tokens = len(limiter._token_log)

    asyncio.run(limiter.acquire("test content"))

    assert len(limiter._request_log) == initial_requests + 1
    assert len(limiter._token_log) == initial_tokens + 1
