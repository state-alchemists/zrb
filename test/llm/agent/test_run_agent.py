import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent, AgentRunResultEvent

from zrb.llm.agent.run_agent import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_run_agent_invokes_history_processors_exactly_once():
    """Processors registered via create_agent must fire exactly once per
    run_agent call — not zero (forgotten), not twice (double-execution)."""
    from zrb.llm.agent.common import create_agent

    call_counts = {"p1": 0, "p2": 0}

    async def p1(msgs):
        call_counts["p1"] += 1
        return msgs

    async def p2(msgs):
        call_counts["p2"] += 1
        return msgs

    agent = create_agent(
        model="openai:gpt-4o-mini",
        system_prompt="test",
        history_processors=[p1, p2],
        yolo=True,
    )

    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "AI result"
    assert call_counts == {"p1": 1, "p2": 1}


@pytest.mark.asyncio
async def test_run_agent_without_history_processors_does_not_crash():
    """An agent created without history_processors must still run."""
    from zrb.llm.agent.common import create_agent

    agent = create_agent(
        model="openai:gpt-4o-mini", system_prompt="test", yolo=True
    )

    mock_result = MagicMock()
    mock_result.output = "ok"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    result, _ = await run_agent(
        agent=agent, message="hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "ok"


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
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "AI result"
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_run_agent_with_attachments():
    """Test run_agent with attachments (BinaryContent)."""
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

    from pydantic_ai import BinaryContent

    # BinaryContent is a proper attachment type (e.g., image data)
    attachments = [BinaryContent(data=b"fake image data", media_type="image/png")]

    result, history = await run_agent(
        agent=agent,
        message="See attachment",
        message_history=[],
        attachments=attachments,
        limiter=LLMLimiter(),
    )
    assert result == "AI result"
    # run_stream_events receives list[UserContent] directly (str + BinaryContent)
    assert len(captured_message) == 1
    msg = captured_message[0]
    assert isinstance(msg, list)
    assert "See attachment" in msg[0]  # First item is the text string
    from pydantic_ai import BinaryContent as _BC

    assert isinstance(msg[1], _BC)  # Second item is the attachment


@pytest.mark.asyncio
async def test_run_agent_error_history_attachment():
    """Test that run_agent attaches history to exceptions."""
    agent = MagicMock()

    async def mock_run_stream_events(*args, **kwargs):
        raise Exception("API Error")
        yield  # Make it a generator

    agent.run_stream_events = mock_run_stream_events

    try:
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
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
        agent=agent, message="", message_history=[], limiter=LLMLimiter()
    )
    assert result == "Resumed"


@pytest.mark.asyncio
async def test_run_agent_deferred_requests():
    """Test run_agent handling deferred tool requests."""
    from pydantic_ai import DeferredToolRequests, DeferredToolResults

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

    # Mock tool resolution - return proper DeferredToolResults object
    with patch(
        "zrb.llm.agent.run_agent._process_deferred_requests", new_callable=AsyncMock
    ) as mock_process:
        mock_deferred_results = MagicMock(spec=DeferredToolResults)
        mock_deferred_results.approvals = {}  # Empty approvals (all tools approved)
        mock_process.return_value = mock_deferred_results

        result, _ = await run_agent(
            agent=agent, message="Use tool", message_history=[], limiter=LLMLimiter()
        )
        assert result == "Final with tool"
        assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_session_end_replace_response_false():
    """Test SESSION_END hook with replace_response=False returns original response."""
    agent = MagicMock()

    # Original response from LLM
    mock_original_result = MagicMock()
    mock_original_result.output = "Original AI response"
    mock_original_result.all_messages.return_value = []

    # Extended session response (should NOT be returned)
    mock_extended_result = MagicMock()
    mock_extended_result.output = "Extended session response"
    mock_extended_result.all_messages.return_value = []

    call_count = 0

    async def mock_run_stream_events(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_original_result)
        else:
            yield AgentRunResultEvent(result=mock_extended_result)

    agent.run_stream_events = mock_run_stream_events

    # Stateful hook that only fires once (prevents infinite loop)
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.SESSION_END:
                if not self.fired:
                    self.fired = True
                    return HookResult.with_system_message(
                        "Side effect message", replace_response=False
                    )
            return HookResult()

    manager = HookManager()
    manager.register(OnceHook(), events=[HookEvent.SESSION_END])

    result, history = await run_agent(
        agent=agent,
        message="Test message",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # Should return ORIGINAL response (replace_response=False)
    assert result == "Original AI response"
    assert call_count == 2  # Original + extended session


@pytest.mark.asyncio
async def test_run_agent_session_end_replace_response_true():
    """Test SESSION_END hook with replace_response=True returns extended response."""
    agent = MagicMock()

    # Original response from LLM
    mock_original_result = MagicMock()
    mock_original_result.output = "Original AI response"
    mock_original_result.all_messages.return_value = []

    # Extended session response (should BE returned)
    mock_transformed_result = MagicMock()
    mock_transformed_result.output = "Transformed response"
    mock_transformed_result.all_messages.return_value = []

    call_count = 0

    async def mock_run_stream_events(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_original_result)
        else:
            yield AgentRunResultEvent(result=mock_transformed_result)

    agent.run_stream_events = mock_run_stream_events

    # Stateful hook that only fires once (prevents infinite loop)
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.SESSION_END:
                if not self.fired:
                    self.fired = True
                    return HookResult.with_system_message(
                        "Summarize the above.", replace_response=True
                    )
            return HookResult()

    manager = HookManager()
    manager.register(OnceHook(), events=[HookEvent.SESSION_END])

    result, history = await run_agent(
        agent=agent,
        message="Test message",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # Should return TRANSFORMED response (replace_response=True)
    assert result == "Transformed response"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_session_end_multiple_hooks():
    """Test multiple SESSION_END hooks - last systemMessage wins."""
    agent = MagicMock()

    mock_result = MagicMock()
    mock_result.output = "Response"
    mock_result.all_messages.return_value = []

    call_count = 0

    async def mock_run_stream_events(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    # Stateful hook that fires only once
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.SESSION_END:
                if not self.fired:
                    self.fired = True
                    return HookResult.with_system_message(
                        "Process this", replace_response=False
                    )
            return HookResult()

    # First hook returns no systemMessage
    async def hook1(context: HookContext) -> HookResult:
        return HookResult()  # No modification

    manager = HookManager()
    manager.register(hook1, events=[HookEvent.SESSION_END])
    manager.register(OnceHook(), events=[HookEvent.SESSION_END])

    result, history = await run_agent(
        agent=agent,
        message="Test message",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # Should return original response
    assert result == "Response"
    assert call_count == 2  # Original + extended
