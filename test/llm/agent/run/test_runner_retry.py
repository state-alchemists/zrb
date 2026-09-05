from unittest.mock import MagicMock

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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )

    assert result == "Recovered"
    # Second request's history had the trailing (empty) ModelResponse trimmed,
    # leaving only the ModelRequest.
    second = histories[1]
    assert [type(m).__name__ for m in second] == ["ModelRequest"]


@pytest.mark.asyncio
async def test_stop_event_turn_slice_correct_after_empty_completion_retry():
    """After an empty-completion retry re-bases `current_history`, the Stop
    hook's `turn` slice and `wrote_files` gate must reflect only the
    *successful* retry's new messages — not the discarded empty attempt, and
    not the whole conversation."""
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )

    captured: list = []

    async def record(context: HookContext) -> HookResult:
        captured.append(context.event_data)
        return HookResult(success=True)

    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.STOP])

    agent = MagicMock()
    empty = MagicMock()
    empty.output = ""
    empty.all_messages.return_value = [
        ModelRequest(parts=[UserPromptPart(content="Hi")]),
        ModelResponse(parts=[TextPart(content="")]),  # the degenerate turn
    ]
    good = MagicMock()
    good.output = "Recovered"
    good.all_messages.return_value = [
        ModelRequest(parts=[UserPromptPart(content="Hi")]),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="Write", args={"path": "x"}, tool_call_id="1")
            ]
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Write", content="ok", tool_call_id="1")]
        ),
        ModelResponse(parts=[TextPart(content="Recovered")]),
    ]

    call_count = 0

    async def _gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield AgentRunResultEvent(result=empty if call_count == 1 else good)

    agent.run = _run_from(_gen)

    result, _ = await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "Recovered"
    assert call_count == 2
    assert len(captured) == 1  # Stop only fires once, on the successful retry
    # Just the retry's own new messages: the tool call, its return, and the
    # final text — not the original UserPromptPart request already counted in
    # current_history before this iteration.
    assert len(captured[0]["turn"]) == 3
    assert captured[0]["wrote_files"] is True


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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

    with pytest.raises(RuntimeError, match="empty response"):
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
        )

    # 1 original attempt + max_empty_completion_retries (2) = 3 stream calls.
    assert call_count == 3
