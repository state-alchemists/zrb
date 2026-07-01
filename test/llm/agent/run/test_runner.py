import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent, AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def _stream_from(agen_func):
    """Wrap an async generator function into a run_stream_events mock.

    ``run_stream_events()`` returns a bare async context manager (no dedicated
    class to import), so we mimic that shape directly with
    ``contextlib.asynccontextmanager`` rather than depending on an internal
    pydantic-ai type.
    """

    @asynccontextmanager
    async def wrapper(*args, **kwargs):
        yield agen_func(*args, **kwargs)

    return wrapper


@pytest.mark.asyncio
async def test_run_agent_runs_history_processors_before_pruning():
    """run_agent runs processors in order before fit_context_window, so
    summarization compresses the history before any hard pruning can cut it.
    (pydantic-ai re-runs them per-request inside run_stream_events; that's a
    separate, idempotent pass.)"""
    from zrb.llm.agent.common import create_agent

    calls = []

    async def p1(msgs, system_prompt_overhead: int = 0):
        calls.append("p1")
        return msgs

    async def p2(msgs, system_prompt_overhead: int = 0):
        calls.append("p2")
        return msgs

    agent = create_agent(
        model="openai-chat:gpt-4o-mini",
        system_prompt="test",
        history_processors=[p1, p2],
        yolo=True,
    )

    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "AI result"
    # Order is preserved; both processors were invoked in zrb's pre-prune pass.
    assert calls == ["p1", "p2"]


@pytest.mark.asyncio
async def test_run_agent_precompact_block_skips_history_processors():
    """A PreCompact hook returning decision=block skips summarization (the
    history processors) for the turn — Claude-compatible blocking PreCompact."""
    from zrb.llm.agent.common import create_agent

    calls = []

    async def p1(msgs, system_prompt_overhead: int = 0):
        calls.append("p1")
        return msgs

    agent = create_agent(
        model="openai-chat:gpt-4o-mini",
        system_prompt="test",
        history_processors=[p1],
        yolo=True,
    )

    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    async def blocking_precompact(ctx):
        return HookResult.block("preserve everything")

    manager = HookManager(search_dirs=[])
    manager.register(blocking_precompact, events=[HookEvent.PRE_COMPACT])

    result, _ = await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )
    assert result == "AI result"
    # The processor never ran because PreCompact blocked compaction.
    assert calls == []


@pytest.mark.asyncio
async def test_run_agent_passes_system_prompt_overhead_to_processors():
    """run_agent passes system-prompt token count as system_prompt_overhead to each processor."""
    from zrb.llm.agent.common import create_agent

    received_overheads = []

    async def capturing_processor(msgs, system_prompt_overhead: int = 0):
        received_overheads.append(system_prompt_overhead)
        return msgs

    agent = create_agent(
        model="openai-chat:gpt-4o-mini",
        system_prompt="test",
        history_processors=[capturing_processor],
        yolo=True,
    )

    mock_result = MagicMock()
    mock_result.output = "ok"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 1000
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = lambda h, m, r: h
    # count_tokens("sys prompt") returns 42; subsequent calls return 0
    limiter.count_tokens.side_effect = [42] + [0] * 20

    await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=limiter,
        system_prompt="sys prompt",
    )

    assert received_overheads == [42]


@pytest.mark.asyncio
async def test_run_agent_appends_live_context_to_user_turn():
    """A non-empty live_context is appended to the end of the user turn.

    This is what keeps the system prompt byte-stable for caching — the volatile
    block rides in the user message, not the instructions.
    """
    from zrb.llm.agent.common import create_agent

    agent = create_agent(
        model="openai-chat:gpt-4o-mini", system_prompt="test", yolo=True
    )

    seen = {}
    mock_result = MagicMock()
    mock_result.output = "ok"
    mock_result.all_messages.return_value = []

    async def _gen(current_message, *args, **kwargs):
        seen["message"] = current_message
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    live = "<live-context>\n- Time: 2026-01-01 00:00:00\n</live-context>"
    await run_agent(
        agent=agent,
        message="Hello",
        message_history=[],
        limiter=LLMLimiter(),
        live_context=live,
    )

    assert "Hello" in seen["message"]
    assert "<live-context>" in seen["message"]
    # Live block trails the user's text (recency).
    assert seen["message"].index("Hello") < seen["message"].index("<live-context>")


@pytest.mark.asyncio
async def test_run_agent_without_live_context_leaves_message_unchanged():
    """The default empty live_context is a no-op — legacy behaviour preserved."""
    from zrb.llm.agent.common import create_agent

    agent = create_agent(
        model="openai-chat:gpt-4o-mini", system_prompt="test", yolo=True
    )

    seen = {}
    mock_result = MagicMock()
    mock_result.output = "ok"
    mock_result.all_messages.return_value = []

    async def _gen(current_message, *args, **kwargs):
        seen["message"] = current_message
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    await run_agent(
        agent=agent, message="Hello", message_history=[], limiter=LLMLimiter()
    )

    assert seen["message"] == "Hello"
    assert "<live-context>" not in seen["message"]


@pytest.mark.asyncio
async def test_run_agent_without_history_processors_does_not_crash():
    """An agent created without history_processors must still run."""
    from zrb.llm.agent.common import create_agent

    agent = create_agent(
        model="openai-chat:gpt-4o-mini", system_prompt="test", yolo=True
    )

    mock_result = MagicMock()
    mock_result.output = "ok"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    result, history = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "AI result"
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_run_agent_fires_stop_on_natural_completion():
    """A completed turn fires HookEvent.STOP — the per-turn "done" signal that
    Claude-Code-compatible consumers (completion sounds, desktop notifications,
    e.g. peon-ping) listen on, not just the manual-interrupt path in the TUI."""
    fired: list[HookEvent] = []

    async def record(context: HookContext) -> HookResult:
        fired.append(context.event)
        return HookResult(success=True)

    manager = HookManager(search_dirs=[])
    manager.register(record, events=[HookEvent.STOP])

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "done"
    assert HookEvent.STOP in fired


@pytest.mark.asyncio
async def test_run_agent_with_attachments():
    """Test run_agent with attachments (BinaryContent)."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []

    # Track the message passed to run_stream_events
    captured_message = []

    async def _gen(message, **kwargs):
        captured_message.append(message)
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        raise Exception("API Error")
        yield  # Make it a generator

    agent.run_stream_events = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_result)
        else:
            yield AgentRunResultEvent(result=mock_final_result)

    agent.run_stream_events = _stream_from(_gen)

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
@pytest.mark.parametrize(
    "calls, approvals",
    [
        pytest.param({}, {"call_id": "approved"}, id="approval-style-deferral"),
        pytest.param({"call_id": "data"}, {}, id="calls-style-deferral"),
    ],
)
async def test_run_agent_deferred_never_reapplies_processors(calls, approvals):
    """History processors are never reapplied between deferred-tool iterations
    (ADR-0058 Fix B), regardless of what current_results looks like.

    This used to be a conditional guard (skip only when current_results had
    pending calls/approvals), but _process_deferred_requests always populates
    current_results.approvals for every resolved call (approved, denied, or
    hook-blocked alike), so the guard's condition was always true in
    practice -- the dead reapplication branch and the now-always-true guard
    were removed in favor of always feeding run_history through unchanged.
    """
    from pydantic_ai import DeferredToolRequests, DeferredToolResults

    processor_calls = []

    async def counting_processor(messages, reserved_tokens=0):
        processor_calls.append(len(messages))
        return messages

    agent = MagicMock()
    agent.zrb_history_processors = [counting_processor]

    mock_result = MagicMock()
    mock_deferred = MagicMock(spec=DeferredToolRequests)
    mock_result.output = mock_deferred
    mock_result.all_messages.return_value = []

    mock_final_result = MagicMock()
    mock_final_result.output = "Final"
    mock_final_result.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_result)
        else:
            yield AgentRunResultEvent(result=mock_final_result)

    agent.run_stream_events = _stream_from(_gen)

    with patch(
        "zrb.llm.agent.run.runner._process_deferred_requests",
        new_callable=AsyncMock,
    ) as mock_process:
        mock_deferred_results = MagicMock(spec=DeferredToolResults)
        mock_deferred_results.calls = calls
        mock_deferred_results.approvals = approvals
        mock_process.return_value = mock_deferred_results

        result, _ = await run_agent(
            agent=agent,
            message="Use tool",
            message_history=[],
            limiter=LLMLimiter(),
        )

        assert result == "Final"
        # Only _prepare_history's up-front pass invokes the processor -- never
        # a second time for the deferred-tool continuation.
        assert len(processor_calls) == 1


@pytest.mark.asyncio
async def test_run_agent_deferred_mismatch_recovers_without_crash():
    """A deferred-mismatch UserError mid-stream is recovered, not raised.

    Regression: the clear_results retry path used to leave new_history=None,
    which the loop fed into sanitize_history(None) and crashed with TypeError.
    With the fix the handler returns the intact run_history, so the loop
    sanitizes a real list and the next iteration succeeds.
    """
    from pydantic_ai.exceptions import UserError as PydanticUserError

    agent = MagicMock()
    mock_final_result = MagicMock()
    mock_final_result.output = "Final"
    mock_final_result.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PydanticUserError(
                "Tool call results were provided, but the message history "
                "does not contain any unprocessed tool calls."
            )
            yield  # pragma: no cover  (makes this an async generator)
        else:
            yield AgentRunResultEvent(result=mock_final_result)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent,
        message="Use tool",
        message_history=[],
        limiter=LLMLimiter(),
    )

    assert result == "Final"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_retries_empty_completion_then_succeeds():
    """An empty-string completion is regenerated, not surfaced as the answer."""
    agent = MagicMock()
    empty = MagicMock()
    empty.output = ""
    empty.all_messages.return_value = []
    good = MagicMock()
    good.output = "Real answer"
    good.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=empty if call_count == 1 else good)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )

    assert result == "Real answer"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_retries_tool_call_placeholder_leak():
    """The '(tool call)' placeholder leaking as output is treated as empty."""
    agent = MagicMock()
    leak = MagicMock()
    leak.output = "(tool call)"
    leak.all_messages.return_value = []
    good = MagicMock()
    good.output = "Done"
    good.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=leak if call_count == 1 else good)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )

    assert result == "Done"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_empty_completion_retry_trims_trailing_response():
    """On retry the degenerate trailing ModelResponse is dropped from history."""
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    agent = MagicMock()
    empty = MagicMock()
    empty.output = ""
    empty.all_messages.return_value = [
        ModelRequest(parts=[UserPromptPart(content="Hi")]),
        ModelResponse(parts=[TextPart(content="")]),  # the degenerate turn
    ]
    good = MagicMock()
    good.output = "Recovered"
    good.all_messages.return_value = []

    call_count = 0
    histories = []

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        histories.append(kwargs.get("message_history"))
        yield AgentRunResultEvent(result=empty if call_count == 1 else good)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )

    assert result == "Recovered"
    # Second request's history had the trailing (empty) ModelResponse trimmed,
    # leaving only the ModelRequest.
    second = histories[1]
    assert [type(m).__name__ for m in second] == ["ModelRequest"]


@pytest.mark.asyncio
async def test_run_agent_structured_output_bypasses_empty_guard():
    """A non-str (structured) output is never treated as an empty completion."""
    agent = MagicMock()
    structured = {"answer": 42}
    result_obj = MagicMock()
    result_obj.output = structured
    result_obj.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=result_obj)

    agent.run_stream_events = _stream_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )

    assert result == structured


@pytest.mark.asyncio
async def test_run_agent_empty_completion_raises_after_retries():
    """A persistently empty completion raises a clear error (bounded retries)."""
    agent = MagicMock()
    empty = MagicMock()
    empty.output = ""
    empty.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=empty)

    agent.run_stream_events = _stream_from(_gen)

    with pytest.raises(RuntimeError, match="empty response"):
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
        )

    # 1 original attempt + max_empty_completion_retries (2) = 3 stream calls.
    assert call_count == 3


@pytest.mark.asyncio
async def test_run_agent_stop_replace_response_false():
    """Test STOP hook with replace_response=False returns original response."""
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

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_original_result)
        else:
            yield AgentRunResultEvent(result=mock_extended_result)

    agent.run_stream_events = _stream_from(_gen)

    # Stateful hook that only fires once (prevents infinite loop)
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.STOP:
                if not self.fired:
                    self.fired = True
                    return HookResult(
                        success=True,
                        modifications={
                            "systemMessage": "Side effect message",
                            "replaceResponse": False,
                        },
                    )
            return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(OnceHook(), events=[HookEvent.STOP])

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
async def test_run_agent_stop_replace_response_true():
    """Test STOP hook with replace_response=True returns extended response."""
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

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_original_result)
        else:
            yield AgentRunResultEvent(result=mock_transformed_result)

    agent.run_stream_events = _stream_from(_gen)

    # Stateful hook that only fires once (prevents infinite loop)
    class OnceHook:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.STOP:
                if not self.fired:
                    self.fired = True
                    return HookResult(
                        success=True,
                        modifications={
                            "systemMessage": "Summarize the above.",
                            "replaceResponse": True,
                        },
                    )
            return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(OnceHook(), events=[HookEvent.STOP])

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


def _single_turn_agent(output="ok"):
    """A mock agent whose stream yields one result and then ends."""
    agent = MagicMock()
    result = MagicMock()
    result.output = output
    result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=result)

    agent.run_stream_events = _stream_from(_gen)
    return agent


@pytest.mark.asyncio
async def test_session_start_source_startup_vs_resume():
    """SESSION_START reports source=startup for a fresh history and resume for a
    populated one, so Claude-style startup/resume matchers work."""
    captured: list[str] = []

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.SESSION_START:
            captured.append(context.source)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(rec, events=[HookEvent.SESSION_START])

    await run_agent(
        agent=_single_turn_agent(),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )
    await run_agent(
        agent=_single_turn_agent(),
        message="again",
        message_history=["prior turn"],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured == ["startup", "resume"]


@pytest.mark.asyncio
async def test_user_prompt_submit_populates_prompt_field():
    """UserPromptSubmit must populate context.prompt so matchers (mapped to the
    `prompt` field) and the CLAUDE_PROMPT env var see the submitted text."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.USER_PROMPT_SUBMIT:
            captured["prompt"] = context.prompt
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(rec, events=[HookEvent.USER_PROMPT_SUBMIT])

    await run_agent(
        agent=_single_turn_agent(),
        message="hello world",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("prompt") == "hello world"


@pytest.mark.asyncio
async def test_pre_compact_trigger_and_additional_context():
    """PRE_COMPACT fires with trigger=auto and its additionalContext is injected
    ahead of summarization."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.PRE_COMPACT:
            captured["trigger"] = context.trigger
            return HookResult(
                success=True, modifications={"additionalContext": "keep the steps"}
            )
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(rec, events=[HookEvent.PRE_COMPACT])

    await run_agent(
        agent=_single_turn_agent(),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("trigger") == "auto"


@pytest.mark.asyncio
async def test_post_compact_fires_after_processing():
    """POST_COMPACT fires (mirror of PreCompact) with trigger=auto once history
    processing has run."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.POST_COMPACT:
            captured["trigger"] = context.trigger
            captured["fired"] = True
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(rec, events=[HookEvent.POST_COMPACT])

    await run_agent(
        agent=_single_turn_agent(),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured.get("fired") is True
    assert captured.get("trigger") == "auto"


@pytest.mark.asyncio
async def test_stop_failure_fires_on_unrecoverable_error():
    """When a turn ends on an unrecoverable error, STOP_FAILURE fires with a
    classified error_type and the original exception still propagates."""
    captured: dict = {}

    async def rec(context: HookContext) -> HookResult:
        if context.event == HookEvent.STOP_FAILURE:
            captured["error_type"] = context.error_type
            captured["error"] = context.error
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(rec, events=[HookEvent.STOP_FAILURE])

    agent = MagicMock()

    async def _gen(*args, **kwargs):
        raise ValueError("bad request")
        yield  # pragma: no cover — marks this a generator

    agent.run_stream_events = _stream_from(_gen)

    with pytest.raises(ValueError):
        await run_agent(
            agent=agent,
            message="hi",
            message_history=[],
            limiter=LLMLimiter(),
            hook_manager=manager,
        )

    assert captured.get("error_type") == "unknown"
    assert "bad request" in (captured.get("error") or "")


@pytest.mark.asyncio
async def test_run_agent_user_prompt_submit_block_ends_turn():
    """A UserPromptSubmit hook that blocks ends the turn before the model runs;
    the reason is surfaced as the output."""
    agent = MagicMock()
    agent.run_stream_events = MagicMock(
        side_effect=AssertionError("model must not run when prompt is blocked")
    )

    async def blocking_hook(context: HookContext) -> HookResult:
        if context.event == HookEvent.USER_PROMPT_SUBMIT:
            return HookResult.block("policy violation")
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(blocking_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    result, history = await run_agent(
        agent=agent,
        message="do something",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "policy violation"


@pytest.mark.asyncio
async def test_run_agent_stop_block_continues_turn():
    """A STOP hook returning decision=block re-runs the agent with the reason
    injected; the continued response is returned."""
    agent = MagicMock()
    first = MagicMock()
    first.output = "first answer"
    first.all_messages.return_value = []
    second = MagicMock()
    second.output = "continued answer"
    second.all_messages.return_value = []

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=first if call_count == 1 else second)

    agent.run_stream_events = _stream_from(_gen)

    class BlockOnce:
        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.STOP and not self.fired:
                self.fired = True
                return HookResult(
                    success=False,
                    should_stop=True,
                    modifications={"decision": "block", "reason": "keep going"},
                )
            return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(BlockOnce(), events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "continued answer"
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_agent_stop_block_cap_prevents_infinite_loop():
    """A STOP hook that always blocks is overridden after the block cap so the
    agent cannot loop forever."""
    from zrb.llm.agent.run.session_extension import STOP_HOOK_BLOCK_CAP

    agent = MagicMock()

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.output = f"turn {call_count}"
        result.all_messages.return_value = []
        yield AgentRunResultEvent(result=result)

    agent.run_stream_events = _stream_from(_gen)

    async def always_block(context: HookContext) -> HookResult:
        if context.event == HookEvent.STOP:
            return HookResult(
                success=False,
                should_stop=True,
                modifications={"decision": "block", "reason": "more"},
            )
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(always_block, events=[HookEvent.STOP])

    result, history = await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    # First turn + STOP_HOOK_BLOCK_CAP continuations, then the cap forces a stop.
    assert call_count == STOP_HOOK_BLOCK_CAP + 1


@pytest.mark.asyncio
async def test_run_agent_session_start_context_prepending():
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    manager = HookManager(search_dirs=[])

    async def session_start_hook(ctx):
        return HookResult(
            success=True, modifications={"additionalContext": "INIT_CONTEXT"}
        )

    manager.register(session_start_hook, events=[HookEvent.SESSION_START])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r: h
    limiter.acquire = AsyncMock()

    with patch.object(agent, "run_stream_events") as mock_run:
        mock_run.side_effect = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    manager = HookManager(search_dirs=[])

    async def prompt_hook(ctx):
        return HookResult(
            success=True, modifications={"additionalContext": "PROMPT_CONTEXT"}
        )

    manager.register(prompt_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r: h
    limiter.acquire = AsyncMock()

    with patch.object(agent, "run_stream_events") as mock_run:
        mock_run.side_effect = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

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

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run_stream_events = _stream_from(_gen)

    # History ends with ModelRequest
    history = [ModelRequest(parts=[])]

    limiter = MagicMock(spec=LLMLimiter)
    limiter.acquire = AsyncMock()
    limiter.max_token_per_request = 1000
    limiter.count_tokens.return_value = 10
    limiter.fit_context_window.side_effect = lambda h, m, r: h

    with patch.object(agent, "run_stream_events") as mock_run:
        mock_run.side_effect = _stream_from(_gen)

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
        # The merge must NOT mutate the caller's original message object in
        # place. The loaded ModelRequest is aliased to the caller's history (and
        # to FileHistoryManager's cached list); an in-place append would graft
        # this turn's prompt onto the stored message and duplicate it on the next
        # save/cancel path. The original object's parts must stay empty.
        assert history[0].parts == []
