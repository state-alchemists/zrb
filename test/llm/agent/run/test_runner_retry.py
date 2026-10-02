from unittest.mock import MagicMock, patch

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
    hook's `turn` slice and `wrote_files` gate must reflect the turn's prompt
    and the *successful* retry's new messages — not the discarded empty
    attempt, and not the whole conversation."""
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
    # The turn's prompt, then the retry's tool call, its return, and the final
    # text — the discarded empty response is not part of it.
    turn = captured[0]["turn"]
    assert [type(m).__name__ for m in turn] == [
        "ModelRequest",
        "ModelResponse",
        "ModelRequest",
        "ModelResponse",
    ]
    assert isinstance(turn[0].parts[0], UserPromptPart)
    assert all(
        not (isinstance(p, TextPart) and p.content == "")
        for m in turn
        for p in m.parts
    )
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


class _Unavailable(Exception):
    status_code = 503


@pytest.mark.asyncio
async def test_transient_provider_error_is_retried_within_one_task_attempt():
    """A 503 is retried inside `run_agent` — the task never sees it."""
    calls = []
    good = MagicMock()
    good.output = "Real answer"
    good.all_messages.return_value = []
    agent = MagicMock()

    async def fake_run(*args, **kwargs):
        calls.append(1)
        if len(calls) <= 2:
            raise _Unavailable("Service Unavailable")
        return good

    agent.run = fake_run

    with patch("asyncio.sleep"):
        result, _ = await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
        )

    assert result == "Real answer"
    assert len(calls) == 3  # 1 original + 2 retries (LLM_API_MAX_RETRIES=3)


@pytest.mark.asyncio
@pytest.mark.parametrize("max_retries,expected_calls", [(0, 1), (1, 1), (3, 3), (5, 5)])
async def test_api_max_retries_caps_total_provider_calls(
    monkeypatch, max_retries, expected_calls
):
    """`LLM_API_MAX_RETRIES` is the TOTAL attempt count, not the retry count —
    0 and 1 both mean "try once"."""
    monkeypatch.setenv("ZRB_LLM_API_MAX_RETRIES", str(max_retries))
    calls = []
    agent = MagicMock()

    async def fake_run(*args, **kwargs):
        calls.append(1)
        raise _Unavailable("Service Unavailable")

    agent.run = fake_run

    with patch("asyncio.sleep"), pytest.raises(_Unavailable):
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
        )

    assert len(calls) == expected_calls


@pytest.mark.asyncio
async def test_stop_event_keeps_earlier_rounds_after_empty_completion_retry():
    """A turn that wrote a file, then produced an empty completion, still
    reports the write — and the prompt — to the Stop hook after the retry."""
    from pydantic_ai import Agent
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel

    model_calls = 0

    async def stream_fn(messages, info):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            yield {
                0: DeltaToolCall(
                    name="Write",
                    json_args='{"path": "a.txt", "content": "x"}',
                    tool_call_id="c1",
                )
            }
        elif model_calls == 2:
            yield " "
        else:
            yield "done"

    agent = Agent(FunctionModel(stream_function=stream_fn))

    @agent.tool_plain(name="Write")
    def write(path: str, content: str) -> str:
        return "ok"

    captured: list = []

    async def record(context: HookContext) -> HookResult:
        captured.append(context.event_data)
        return HookResult(success=True)

    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.STOP])

    result, _ = await run_agent(
        agent=agent,
        message="from now on always use tabs. write a.txt",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert result == "done"
    assert model_calls == 3
    assert len(captured) == 1
    assert captured[0]["wrote_files"] is True
    assert captured[0]["changed_paths"] == ["a.txt"]
    assert captured[0]["journal_worthy"] is True


@pytest.mark.asyncio
async def test_invalid_tool_call_retry_keeps_multimodal_prompt():
    """The corrective retry of a turn with an attachment still carries the
    user's request and the attachment."""
    from pydantic_ai import Agent, BinaryContent
    from pydantic_ai.exceptions import ModelHTTPError
    from pydantic_ai.messages import UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    retried_with: list = []

    async def stream_fn(messages, info):
        if not retried_with and not any(
            "BROKEN" in str(p.content)
            for m in messages
            for p in m.parts
            if isinstance(p, UserPromptPart)
        ):
            raise ModelHTTPError(
                status_code=400,
                model_name="m",
                body={"message": "unknown tool: ReadRead"},
            )
        retried_with.extend(
            item
            for m in messages
            for p in m.parts
            if isinstance(p, UserPromptPart)
            for item in (p.content if isinstance(p.content, list) else [p.content])
        )
        yield "ok"

    attachment = BinaryContent(data=b"hello", media_type="text/plain")
    result, _ = await run_agent(
        agent=Agent(FunctionModel(stream_function=stream_fn)),
        message="SUMMARIZE THE REPORT",
        message_history=[],
        attachments=[attachment],
        limiter=LLMLimiter(),
    )

    assert result == "ok"
    texts = [item for item in retried_with if isinstance(item, str)]
    assert any("SUMMARIZE THE REPORT" in text for text in texts)
    assert any("BROKEN" in text for text in texts)
    assert any(
        isinstance(item, BinaryContent) and item.data == b"hello"
        for item in retried_with
    )
