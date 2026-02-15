import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic_ai import Agent, AgentRunResultEvent
from zrb.llm.agent.run_agent import run_agent
from zrb.llm.config.limiter import LLMLimiter

@pytest.mark.asyncio
async def test_run_agent_basic():
    """Test basic run_agent execution."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []
    
    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)
        
    agent.run_stream_events = mock_run_stream_events
    
    result, history = await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter()
    )
    assert result == "AI result"
    assert isinstance(history, list)

@pytest.mark.asyncio
async def test_run_agent_with_attachments():
    """Test run_agent with attachments."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []
    
    # Track the message passed to run_stream_events
    captured_message = []
    async def mock_run_stream_events(message, **kwargs):
        captured_message.append(message)
        yield AgentRunResultEvent(result=mock_result)
        
    agent.run_stream_events = mock_run_stream_events
    
    from pydantic_ai.messages import UserPromptPart
    attachments = [UserPromptPart(content="file content")]
    
    result, history = await run_agent(
        agent=agent,
        message="See attachment",
        message_history=[],
        attachments=attachments,
        limiter=LLMLimiter()
    )
    assert result == "AI result"
    assert any("See attachment" in str(p) for p in captured_message[0])

@pytest.mark.asyncio
async def test_run_agent_error_history_attachment():
    """Test that run_agent attaches history to exceptions."""
    agent = MagicMock()
    async def mock_run_stream_events(*args, **kwargs):
        raise Exception("API Error")
        yield # Make it a generator
        
    agent.run_stream_events = mock_run_stream_events
    
    try:
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=LLMLimiter()
        )
    except Exception as e:
        assert hasattr(e, "zrb_history")
        assert isinstance(e.zrb_history, list)

@pytest.mark.asyncio
async def test_run_agent_empty_message():
    """Test run_agent with empty message (e.g. only attachments or just resuming)."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Resumed"
    mock_result.all_messages.return_value = []
    
    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)
        
    agent.run_stream_events = mock_run_stream_events
    
    result, _ = await run_agent(
        agent=agent,
        message="",
        message_history=[],
        limiter=LLMLimiter()
    )
    assert result == "Resumed"

@pytest.mark.asyncio
async def test_run_agent_deferred_requests():
    """Test run_agent handling deferred tool requests."""
    from pydantic_ai import DeferredToolRequests
    agent = MagicMock()
    mock_result = MagicMock()
    mock_deferred = MagicMock(spec=DeferredToolRequests)
    mock_result.output = mock_deferred
    mock_result.all_messages.return_value = []
    
    # Final result after tool resolution
    mock_final_result = MagicMock()
    mock_final_result.output = "Final with tool"
    mock_final_result.all_messages.return_value = []

    call_count = 0
    async def mock_run_stream_events(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_result)
        else:
            yield AgentRunResultEvent(result=mock_final_result)
            
    agent.run_stream_events = mock_run_stream_events
    
    # Mock tool resolution
    with patch("zrb.llm.agent.run_agent._process_deferred_requests", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = ["Tool result"]
        
        result, _ = await run_agent(
            agent=agent,
            message="Use tool",
            message_history=[],
            limiter=LLMLimiter()
        )
        assert result == "Final with tool"
        assert call_count == 2
