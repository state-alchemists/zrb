import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent, AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_run_agent_runs_history_processors_before_pruning():
    """run_agent runs processors in order before fit_context_window, so
    summarization compresses the history before any hard pruning can cut it.
    (pydantic-ai re-runs them per-request inside run_stream_events; that's a
    separate, idempotent pass.)"""
    from zrb.llm.agent.common import create_agent

    calls = []

    async def p1(msgs):
        calls.append("p1")
        return msgs

    async def p2(msgs):
        calls.append("p2")
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
    # Order is preserved; both processors were invoked in zrb's pre-prune pass.
    assert calls == ["p1", "p2"]


@pytest.mark.asyncio
async def test_run_agent_without_history_processors_does_not_crash():
    """An agent created without history_processors must still run."""
    from zrb.llm.agent.common import create_agent

    agent = create_agent(model="openai:gpt-4o-mini", system_prompt="test", yolo=True)

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
        "zrb.llm.agent.run.runner._process_deferred_requests", new_callable=AsyncMock
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
async def test_run_agent_session_start_context_prepending():
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    manager = HookManager()

    async def session_start_hook(ctx):
        return HookResult.with_additional_context("INIT_CONTEXT")

    manager.register(session_start_hook, events=[HookEvent.SESSION_START])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r: h
    limiter.acquire = AsyncMock()

    with patch.object(
        agent, "run_stream_events", side_effect=mock_run_stream_events
    ) as mock_run:
        result, _ = await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            hook_manager=manager,
        )

        # Check history passed to run_stream_events
        passed_history = mock_run.call_args[1]["message_history"]
        assert len(passed_history) == 1
        assert isinstance(passed_history[0], ModelRequest)
        assert isinstance(passed_history[0].parts[0], SystemPromptPart)
        assert passed_history[0].parts[0].content == "INIT_CONTEXT"


@pytest.mark.asyncio
async def test_run_agent_user_prompt_context_prepending():
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    manager = HookManager()

    async def prompt_hook(ctx):
        return HookResult.with_additional_context("PROMPT_CONTEXT")

    manager.register(prompt_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r: h
    limiter.acquire = AsyncMock()

    with patch.object(
        agent, "run_stream_events", side_effect=mock_run_stream_events
    ) as mock_run:
        result, _ = await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            hook_manager=manager,
        )

        # Check message passed to run_stream_events
        passed_message = mock_run.call_args[0][0]
        assert "PROMPT_CONTEXT" in passed_message
        assert "Hi" in passed_message


@pytest.mark.asyncio
async def test_run_agent_multi_ui_resolution():
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    ui1 = MagicMock()
    ui2 = MagicMock()

    limiter = MagicMock(spec=LLMLimiter)
    limiter.acquire = AsyncMock()
    limiter.max_token_per_request = 1000
    limiter.count_tokens.return_value = 10
    limiter.fit_context_window.side_effect = lambda h, m, r: h

    with patch("zrb.llm.ui.multi_ui.MultiUI", return_value=MagicMock()) as mock_multi:
        await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            ui=[ui1, ui2],
        )
        mock_multi.assert_called_once_with([ui1, ui2])


@pytest.mark.asyncio
async def test_run_agent_emergency_pruning():
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 100
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = lambda h, m, r: h

    # Mock history message that is too large
    msg_large = MagicMock()

    # 1. count_tokens(system_prompt) -> 0
    # 2. count_tokens(processed_history) -> 200 (triggers pruning)
    # 3. count_tokens(processed_history[-1]) -> 50
    # 4. count_tokens(pruned_history) in _acquire_rate_limit -> 50
    limiter.count_tokens.side_effect = [0, 200, 50, 50, 50, 50]

    with patch(
        "zrb.llm.agent.run.runner.ensure_alternating_roles", side_effect=lambda x: x
    ):
        result, _ = await run_agent(
            agent=agent, message="Hi", message_history=[msg_large], limiter=limiter
        )
        assert result == "Result"


@pytest.mark.asyncio
async def test_run_agent_merge_consecutive_model_requests():
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def mock_run_stream_events(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = mock_run_stream_events

    # History ends with ModelRequest
    history = [ModelRequest(parts=[])]

    limiter = MagicMock(spec=LLMLimiter)
    limiter.acquire = AsyncMock()
    limiter.max_token_per_request = 1000
    limiter.count_tokens.return_value = 10
    limiter.fit_context_window.side_effect = lambda h, m, r: h

    with patch.object(
        agent, "run_stream_events", side_effect=mock_run_stream_events
    ) as mock_run:
        await run_agent(
            agent=agent, message="Hi", message_history=history, limiter=limiter
        )

        # Check history passed to run_stream_events
        passed_history = mock_run.call_args[1]["message_history"]
        assert len(passed_history) == 1
        assert isinstance(passed_history[0].parts[-1], UserPromptPart)
        assert passed_history[0].parts[-1].content == "Hi"
        # current_message should be None
        assert mock_run.call_args[0][0] is None
