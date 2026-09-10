from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookResult
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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

    async def blocking_precompact(ctx):
        return HookResult.block("preserve everything")

    manager = HookManager(search_dirs=[])
    manager.add_hook(blocking_precompact, events=[HookEvent.PRE_COMPACT])

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

    agent.run = _run_from(_gen)

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 1000
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h
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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

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

    agent.run = _run_from(_gen)

    result, _ = await run_agent(
        agent=agent, message="hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_agent_emergency_pruning():
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    limiter = MagicMock(spec=LLMLimiter)
    limiter.max_token_per_request = 100
    limiter.acquire = AsyncMock()
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h

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

    agent.run = _run_from(_gen)

    # History ends with ModelRequest
    history = [ModelRequest(parts=[])]

    limiter = MagicMock(spec=LLMLimiter)
    limiter.acquire = AsyncMock()
    limiter.max_token_per_request = 1000
    limiter.count_tokens.return_value = 10
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)

        await run_agent(
            agent=agent, message="Hi", message_history=history, limiter=limiter
        )

        # Check history passed to agent.run
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


@pytest.mark.asyncio
async def test_run_agent_error_preserves_live_history_over_stale_baseline():
    """A crash inside the *first* `agent.run()` call of a turn used to lose
    every message produced so far — `run_history` only updates once
    `agent.run()` returns. `partial_run.latest_history` (the live
    `ctx.messages`) preserves it instead, dangling tool call included."""
    from types import SimpleNamespace

    from pydantic_ai import PartStartEvent
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

    agent = MagicMock()
    ctx = SimpleNamespace(messages=[])

    async def _gen(*args, **kwargs):
        # Idempotent across retries: always end up with exactly this one
        # dangling-tool-call response before raising.
        ctx.messages.clear()
        ctx.messages.append(
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args="{}", tool_call_id="c1")]
            )
        )
        yield PartStartEvent(
            index=0, part=TextPart(content=""), previous_part_kind=None
        )
        raise RuntimeError("model connection dropped mid-tool-call")

    agent.run = _run_from_with_ctx(_gen, ctx)

    with pytest.raises(RuntimeError) as excinfo:
        await run_agent(
            agent=agent, message="hi", message_history=[], limiter=LLMLimiter()
        )

    e = excinfo.value
    assert hasattr(e, "zrb_history")
    # The dangling tool call survives — not silently dropped like the stale
    # pre-turn `run_history` ([]) would have done.
    assert len(e.zrb_history) == 1
    assert isinstance(e.zrb_history[0], ModelResponse)
    assert e.zrb_history[0].parts[0].tool_call_id == "c1"
