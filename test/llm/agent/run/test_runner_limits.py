import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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


def _run_from_with_ctx(agen_func, ctx):
    """Like ``_run_from``, but hands the given ``ctx`` (with a live
    ``.messages`` list) to the event_stream_handler instead of a bare
    ``MagicMock()`` — needed to exercise checkpoint-boundary detection, which
    reads ``ctx.messages``.
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
            await handler(ctx, events())
        else:
            async for _ in events():
                pass
        return result_holder[0] if result_holder else None

    return fake_run


def _minimal_limiter() -> MagicMock:
    limiter = MagicMock(spec=LLMLimiter)
    limiter.acquire = AsyncMock()
    limiter.max_token_per_request = 1000
    limiter.count_tokens.return_value = 10
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h
    return limiter


@pytest.mark.asyncio
async def test_run_agent_caps_requests_per_run():
    from zrb.config.config import CFG

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=_minimal_limiter()
        )

    limits = mock_run.call_args[1]["usage_limits"]
    assert limits.request_limit == CFG.LLM_MAX_REQUEST_PER_RUN


@pytest.mark.asyncio
async def test_run_agent_request_cap_can_be_disabled(monkeypatch):
    """0 means "no cap", not "no requests allowed"."""
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "DEFAULT_LLM_MAX_REQUEST_PER_RUN", "0")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_MAX_REQUEST_PER_RUN", raising=False)

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=_minimal_limiter()
        )

    assert mock_run.call_args[1]["usage_limits"].request_limit is None


@pytest.mark.asyncio
async def test_run_agent_explains_the_request_cap_instead_of_retrying():
    """Hitting the cap halts with actionable text, and does not burn retries.

    The generic error path would otherwise surface pydantic-ai's own message,
    which names neither the knob nor why raising it is usually the wrong move.
    """
    from pydantic_ai.exceptions import UsageLimitExceeded

    from zrb.config.config import CFG

    agent = MagicMock()
    attempts = 0

    async def _gen(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise UsageLimitExceeded("the exceeded request_limit of 300")
        yield  # pragma: no cover - generator marker

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)
        with pytest.raises(RuntimeError) as excinfo:
            await run_agent(
                agent=agent,
                message="Hi",
                message_history=[],
                limiter=_minimal_limiter(),
            )

    message = str(excinfo.value)
    assert f"{CFG.LLM_MAX_REQUEST_PER_RUN} model requests" in message
    assert f"{CFG.ENV_PREFIX}_LLM_MAX_REQUEST_PER_RUN" in message
    # A cap is not transient: retrying it re-hits the same wall.
    assert attempts == 1


@pytest.mark.asyncio
async def test_run_agent_checkpoint_fires_at_tool_round_trip_boundaries():
    """checkpoint_fn fires once per safe boundary — `ctx.messages` grows and
    ends in a `ModelRequest` — not on every raw stream event, and never while
    the latest `ModelResponse`'s tool calls are still unresolved."""
    from types import SimpleNamespace

    from pydantic_ai import PartStartEvent
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )

    agent = MagicMock()
    ctx = SimpleNamespace(messages=[])
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = ctx.messages

    def _marker():
        return PartStartEvent(
            index=0, part=TextPart(content=""), previous_part_kind=None
        )

    async def _gen(*args, **kwargs):
        # Mirrors pydantic-ai's own append timing: the user's ModelRequest
        # lands before the model is even asked to respond.
        ctx.messages.append(ModelRequest(parts=[UserPromptPart(content="hi")]))
        yield _marker()

        # Model responds with a tool call — dangling until the tool returns.
        ctx.messages.append(
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args="{}", tool_call_id="c1")]
            )
        )
        yield _marker()

        # Tool result lands, folded into the next request: safe boundary again.
        ctx.messages.append(
            ModelRequest(
                parts=[ToolReturnPart(tool_name="t", content="ok", tool_call_id="c1")]
            )
        )
        yield _marker()

        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from_with_ctx(_gen, ctx)

    checkpoints = []

    async def checkpoint_fn(snapshot):
        checkpoints.append(snapshot)

    await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        checkpoint_fn=checkpoint_fn,
    )

    # Two boundaries crossed: the initial user-request append, and the
    # tool-return request append. The mid-tool-call ModelResponse never
    # triggers a checkpoint on its own (it would be a dangling tool call).
    assert len(checkpoints) == 2
    assert len(checkpoints[0]) == 1
    assert len(checkpoints[1]) == 3
    assert isinstance(checkpoints[1][-1], ModelRequest)
    # Each snapshot is a copy: later growth of ctx.messages must not
    # retroactively change what was already captured and (in production)
    # already handed to a background save task.
    assert checkpoints[0] is not ctx.messages
    assert len(checkpoints[0]) == 1


@pytest.mark.asyncio
async def test_run_agent_checkpoint_awaited_before_run_agent_returns():
    """Background checkpoint tasks are drained before `run_agent` returns, so
    a caller's own end-of-turn save can never race a lagging checkpoint
    write."""
    from types import SimpleNamespace

    from pydantic_ai import PartStartEvent
    from pydantic_ai.messages import ModelRequest, TextPart, UserPromptPart

    agent = MagicMock()
    ctx = SimpleNamespace(messages=[])
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = ctx.messages

    async def _gen(*args, **kwargs):
        ctx.messages.append(ModelRequest(parts=[UserPromptPart(content="hi")]))
        yield PartStartEvent(
            index=0, part=TextPart(content=""), previous_part_kind=None
        )
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from_with_ctx(_gen, ctx)

    checkpoint_finished = False

    async def slow_checkpoint(snapshot):
        nonlocal checkpoint_finished
        await asyncio.sleep(0)
        checkpoint_finished = True

    await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        checkpoint_fn=slow_checkpoint,
    )

    assert checkpoint_finished
