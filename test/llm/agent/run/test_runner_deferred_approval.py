from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter


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
async def test_run_agent_approved_tool_call_lands_in_history_once():
    """A deferred tool call resolved through the real approval cascade (not
    mocked -- `yolo=True` drives `process_deferred_requests`'s own YOLO
    branch) must have its result appear in the returned history exactly
    once, positioned after the call that requested it."""
    from pydantic_ai import DeferredToolRequests
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
    )

    call = ToolCallPart(tool_name="Read", args={"path": "f.txt"}, tool_call_id="call-1")
    round1_messages = [ModelResponse(parts=[call])]
    round1_result = MagicMock()
    round1_result.output = DeferredToolRequests(approvals=[call])
    round1_result.all_messages.return_value = round1_messages

    round2_messages = [
        *round1_messages,
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="Read", content="file body", tool_call_id="call-1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="done")]),
    ]
    round2_result = MagicMock()
    round2_result.output = "done"
    round2_result.all_messages.return_value = round2_messages

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(
            result=round1_result if call_count == 1 else round2_result
        )

    agent = MagicMock()
    agent.run = _run_from(_gen)

    result, history = await run_agent(
        agent=agent,
        message="Read the file",
        message_history=[],
        limiter=LLMLimiter(),
        yolo=True,
    )

    assert result == "done"
    assert call_count == 2
    call_index = next(
        i
        for i, msg in enumerate(history)
        for p in getattr(msg, "parts", [])
        if isinstance(p, ToolCallPart) and p.tool_call_id == "call-1"
    )
    returns = [
        (i, p)
        for i, msg in enumerate(history)
        for p in getattr(msg, "parts", [])
        if isinstance(p, ToolReturnPart) and p.tool_call_id == "call-1"
    ]
    assert len(returns) == 1
    return_index, return_part = returns[0]
    assert return_part.content == "file body"
    assert return_index > call_index


@pytest.mark.asyncio
async def test_run_agent_denied_tool_call_reaches_history_without_running():
    """A deferred tool call denied through the real approval cascade (a
    plain callable `tool_confirmation`, not the CLI/UI path) must have its
    denial text reach history, and pydantic-ai must be told not to execute
    it -- `deferred_tool_results.calls` stays empty for the denied call."""
    from pydantic_ai import DeferredToolRequests, ToolDenied
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
    )

    call = ToolCallPart(
        tool_name="Shell", args={"command": "rm -rf /"}, tool_call_id="call-2"
    )
    round1_messages = [ModelResponse(parts=[call])]
    round1_result = MagicMock()
    round1_result.output = DeferredToolRequests(approvals=[call])
    round1_result.all_messages.return_value = round1_messages

    round2_messages = [
        *round1_messages,
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="Shell",
                    content="Denied by test policy",
                    tool_call_id="call-2",
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="I won't run that")]),
    ]
    round2_result = MagicMock()
    round2_result.output = "I won't run that"
    round2_result.all_messages.return_value = round2_messages

    def deny(call_part):
        return ToolDenied("Denied by test policy")

    call_count = 0
    captured_round2_kwargs = {}

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield AgentRunResultEvent(result=round1_result)
        else:
            captured_round2_kwargs.update(kwargs)
            yield AgentRunResultEvent(result=round2_result)

    agent = MagicMock()
    agent.run = _run_from(_gen)

    result, history = await run_agent(
        agent=agent,
        message="rm -rf /",
        message_history=[],
        limiter=LLMLimiter(),
        tool_confirmation=deny,
    )

    assert result == "I won't run that"
    assert call_count == 2

    # pydantic-ai was told not to execute the denied call.
    deferred_results = captured_round2_kwargs["deferred_tool_results"]
    assert deferred_results.calls == {}
    assert isinstance(deferred_results.approvals["call-2"], ToolDenied)

    # The denial text reaches history, exactly once.
    returns = [
        p
        for msg in history
        for p in getattr(msg, "parts", [])
        if isinstance(p, ToolReturnPart) and p.tool_call_id == "call-2"
    ]
    assert len(returns) == 1
    assert "Denied" in returns[0].content
