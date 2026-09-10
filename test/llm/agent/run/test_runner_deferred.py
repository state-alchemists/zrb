from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def _run_from(agen_func):
    """Wrap an async generator function into an ``agent.run(event_stream_handler=...)`` mock.

    ``agen_func`` keeps yielding the same events every test already
    constructs, ending with ``AgentRunResultEvent(result=...)`` (the old
    ``run_stream_events()`` shape). Real pydantic-ai's ``event_stream_handler``
    never receives that trailing event -- it's ``run_stream_events()``'s own
    addition, synthesized by its consumer-facing iterator after the
    background run finishes. This strips it the same way ``_execution_loop``
    does and returns its ``.result`` as ``agent.run()``'s return value.
    """

    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)
        result_holder = []

        async def events():
            async for event in agen_func(*args, **kwargs):
                if isinstance(event, AgentRunResultEvent):
                    result_holder.append(event.result)
                    return
                yield event

        if handler is not None:
            await handler(MagicMock(), events())
        else:
            async for _ in events():
                pass
        return result_holder[0] if result_holder else None

    return fake_run


@pytest.mark.asyncio
async def test_run_agent_with_attachments():
    """Test run_agent with attachments (BinaryContent)."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []

    # Track the message passed to agent.run
    captured_message = []

    async def _gen(message, **kwargs):
        captured_message.append(message)
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

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
    # agent.run receives list[UserContent] directly (str + BinaryContent)
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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

    # Mock tool resolution - return proper DeferredToolResults object
    with patch(
        "zrb.llm.agent.run.runner.process_deferred_requests", new_callable=AsyncMock
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
async def test_stop_event_wrote_files_true_after_deferred_tool_approval():
    """A tool call that needed human approval (`DeferredToolRequests`) must
    still count toward `wrote_files` on the turn that eventually completes.

    Regression for a real bug: the DeferredToolRequests branch reassigns
    `current_history = run_history` before continuing, which folds the
    approved-but-not-yet-run Write call into what the next iteration's fresh
    `run_history[turn_baseline_len:]` slice would treat as pre-existing
    history — silently excluding it from `wrote_files`/`turn` once Stop
    finally fires. Caught via a live interactive session where a human
    approved a Write and the journal-compliance hook never fired: registered,
    no exception, but the gate was never satisfied because this slice came up
    empty. `turn_messages_acc` (accumulated per iteration, not sliced once at
    the end) is the fix under test here.
    """
    from pydantic_ai import DeferredToolRequests, DeferredToolResults
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
    )

    captured: list = []

    async def record(context: HookContext) -> HookResult:
        captured.append(context.event_data)
        return HookResult(success=True)

    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.STOP])

    agent = MagicMock()

    # Round 1: the model calls Write; pydantic-ai defers it for approval.
    round1_messages = [
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="Write", args={"path": "x"}, tool_call_id="1")
            ]
        )
    ]
    mock_deferred_result = MagicMock()
    mock_deferred_result.output = MagicMock(spec=DeferredToolRequests)
    mock_deferred_result.all_messages.return_value = round1_messages

    # Round 2: after approval, the tool executes and the model replies.
    round2_messages = [
        *round1_messages,
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Write", content="ok", tool_call_id="1")]
        ),
        ModelResponse(parts=[TextPart(content="done")]),
    ]
    mock_final_result = MagicMock()
    mock_final_result.output = "done"
    mock_final_result.all_messages.return_value = round2_messages

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=mock_deferred_result)
        else:
            yield AgentRunResultEvent(result=mock_final_result)

    agent.run = _run_from(_gen)

    with patch(
        "zrb.llm.agent.run.runner.process_deferred_requests", new_callable=AsyncMock
    ) as mock_process:
        mock_deferred_results = MagicMock(spec=DeferredToolResults)
        mock_deferred_results.approvals = {"1": "approved"}
        mock_process.return_value = mock_deferred_results

        await run_agent(
            agent=agent,
            message="Write it",
            message_history=[],
            limiter=LLMLimiter(),
            hook_manager=manager,
        )

    assert len(captured) == 1
    assert captured[0]["wrote_files"] is True
    turn_tool_names = [
        p.tool_name
        for msg in captured[0]["turn"]
        for p in getattr(msg, "parts", [])
        if getattr(p, "part_kind", None) == "tool-call"
    ]
    assert "Write" in turn_tool_names


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
    (ADR-0040 Fix B), regardless of what current_results looks like.

    This used to be a conditional guard (skip only when current_results had
    pending calls/approvals), but process_deferred_requests always populates
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

    agent.run = _run_from(_gen)

    with patch(
        "zrb.llm.agent.run.runner.process_deferred_requests",
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

    agent.run = _run_from(_gen)

    result, _ = await run_agent(
        agent=agent,
        message="Use tool",
        message_history=[],
        limiter=LLMLimiter(),
    )

    assert result == "Final"
    assert call_count == 2
