import pytest
import asyncio
from unittest.mock import MagicMock, patch
from zrb.llm.config.limiter import LLMLimiter
from pydantic_ai.messages import ModelRequest, UserPromptPart

@pytest.mark.asyncio
async def test_llm_limiter_count_tokens():
    limiter = LLMLimiter()
    # Mock tiktoken to avoid dependency issues in tests if not installed
    with patch("zrb.llm.config.limiter.LLMLimiter.use_tiktoken", False):
        tokens = limiter.count_tokens("Hello world")
        # Fallback is len(text) // 3
        assert tokens == 11 // 3

@pytest.mark.asyncio
async def test_llm_limiter_truncate_text():
    limiter = LLMLimiter()
    with patch("zrb.llm.config.limiter.LLMLimiter.use_tiktoken", False):
        text = "A" * 30
        truncated = limiter.truncate_text(text, 5)
        # Fallback approximation (max_tokens * 3)
        assert len(truncated) <= 15

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
    # which for non-tiktoken is len(text) // 3.
    # msg1 tokens = 5 // 3 = 1
    # msg2 tokens = 12 // 3 = 4
    # new_msg tokens = 9 // 3 = 3
    # Total = 1 + 4 + 3 = 8. Limit = 2 * 0.95 = 1.9.
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
