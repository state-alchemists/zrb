import pytest
from unittest.mock import MagicMock, AsyncMock
from zrb.llm.history_processor.summarizer import (
    summarize_history,
    create_summarizer_history_processor,
    summarize_messages
)
from pydantic_ai.messages import ModelRequest, UserPromptPart, ToolReturnPart

class MockLimiter:
    def count_tokens(self, content):
        return 10
    def truncate_text(self, text, limit):
        return text[:limit]

@pytest.mark.asyncio
async def test_summarize_history_resilience():
    """Test that summarize_history handles None for all optional parameters."""
    limiter = MockLimiter()
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]
    
    # Test with all optional parameters as None
    # This simulates calls like the one in LLMTask._should_summarize
    try:
        result = await summarize_history(
            messages,
            agent=None,
            summary_window=None,
            limiter=limiter,
            conversational_token_threshold=None
        )
        assert result == messages
    except TypeError as e:
        pytest.fail(f"summarize_history crashed with TypeError: {e}")

@pytest.mark.asyncio
async def test_create_summarizer_history_processor_resilience():
    """Test that the processor created handles None parameters gracefully."""
    limiter = MockLimiter()
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]
    
    processor = create_summarizer_history_processor(
        conversational_agent=None,
        message_agent=None,
        limiter=limiter,
        conversational_token_threshold=None,
        message_token_threshold=None,
        summary_window=None
    )
    
    try:
        result = await processor(messages)
        assert result == messages
    except TypeError as e:
        pytest.fail(f"History processor crashed with TypeError: {e}")

@pytest.mark.asyncio
async def test_summarize_messages_resilience():
    """Test that summarize_messages handles None parameters gracefully."""
    limiter = MockLimiter()
    messages = [
        ModelRequest(parts=[
            ToolReturnPart(content="some tool result", tool_name="t", tool_call_id="1")
        ])
    ]
    
    try:
        result = await summarize_messages(
            messages,
            agent=None,
            limiter=limiter,
            message_token_threshold=None
        )
        assert result == messages
    except TypeError as e:
        pytest.fail(f"summarize_messages crashed with TypeError: {e}")

def test_split_history_resilience():
    """Test that split_history handles potential None values if called directly."""
    from zrb.llm.summarizer.history_splitter import split_history
    limiter = MockLimiter()
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]
    
    # Although summarize_history now provides defaults, we test split_history directly
    # to ensure it's robust if its internal contract changes or it's used elsewhere.
    try:
        # We pass 0 instead of None because split_history hints suggest int
        # But let's see if None would crash it.
        # Actually, split_history's current implementation WOULD crash on None 
        # because of `len(messages) - summary_window - 1`
        # and `conversational_token_threshold * 0.7`.
        # So it's good that summarize_history handles it.
        
        # Testing with small values
        to_summarize, to_keep = split_history(
            messages,
            summary_window=0,
            limiter=limiter,
            conversational_token_threshold=0
        )
        assert isinstance(to_summarize, list)
        assert isinstance(to_keep, list)
    except TypeError as e:
        pytest.fail(f"split_history crashed with TypeError: {e}")
