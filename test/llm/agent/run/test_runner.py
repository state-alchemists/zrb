import asyncio
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
async def test_run_agent_basic():
    """Test basic run_agent execution."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "AI result"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    result, history = await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )
    assert result == "AI result"
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_run_agent_binds_explicit_run_scope_for_nested_tools():
    """A tool call made mid-run (e.g. file_observation.py's read-before-write
    check) must see the `run_scope` the caller passed in — this is what lets
    it recognize the same conversation across its own separate turns.
    """
    from zrb.llm.agent_state import get_current_agent_run_scope

    seen_scope = None

    async def _gen(*args, **kwargs):
        nonlocal seen_scope
        seen_scope = get_current_agent_run_scope()
        mock_result = MagicMock()
        mock_result.output = "done"
        mock_result.all_messages.return_value = []
        yield AgentRunResultEvent(result=mock_result)

    agent = MagicMock()
    agent.run = _run_from(_gen)

    await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        run_scope="conversation-42",
    )
    assert seen_scope == "conversation-42"


@pytest.mark.asyncio
async def test_run_agent_defaults_run_scope_to_a_fresh_id_each_call():
    """Two runs that don't pass `run_scope` (e.g. two sibling sub-agent
    delegations) must land in *different* scopes — never share one implicit
    bucket, and never collide with each other by construction.
    """
    from zrb.llm.agent_state import get_current_agent_run_scope

    seen_scopes = []

    async def _gen(*args, **kwargs):
        seen_scopes.append(get_current_agent_run_scope())
        mock_result = MagicMock()
        mock_result.output = "done"
        mock_result.all_messages.return_value = []
        yield AgentRunResultEvent(result=mock_result)

    agent = MagicMock()
    agent.run = _run_from(_gen)

    await run_agent(agent=agent, message="Hi", message_history=[], limiter=LLMLimiter())
    await run_agent(agent=agent, message="Hi", message_history=[], limiter=LLMLimiter())

    assert len(seen_scopes) == 2
    assert seen_scopes[0] and seen_scopes[1]
    assert seen_scopes[0] != seen_scopes[1]


@pytest.mark.asyncio
async def test_run_agent_resets_run_scope_after_returning():
    from zrb.llm.agent_state import get_current_agent_run_scope

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)
    assert get_current_agent_run_scope() == ""

    await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        run_scope="conversation-42",
    )
    assert get_current_agent_run_scope() == ""


@pytest.mark.asyncio
async def test_run_agent_feeds_final_result_to_event_handler():
    """`agent.run(event_stream_handler=...)`'s handler never receives a
    trailing `AgentRunResultEvent` -- that's `run_stream_events()`'s own
    synthesis, added by its consumer-facing iterator after the fact.
    `_execution_loop` must re-fire it manually so usage accounting
    (`StreamEventHandler.handle_run_result`) keeps working."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    handler = AsyncMock()
    result, _ = await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        event_handler=handler,
    )

    assert result == "done"
    fired = [call.args[0] for call in handler.await_args_list]
    result_events = [e for e in fired if isinstance(e, AgentRunResultEvent)]
    assert len(result_events) == 1
    assert result_events[0].result is mock_result


@pytest.mark.asyncio
async def test_run_agent_passes_event_stream_handler_to_agent_run():
    """`_execution_loop` calls `agent.run` (not `run_stream_events`) with an
    `event_stream_handler` kwarg, and keeps passing the same
    `message_history`/`deferred_tool_results`/`usage_limits` kwargs
    `run_stream_events` used to receive."""
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)
        await run_agent(
            agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
        )

    assert callable(mock_run.call_args[1]["event_stream_handler"])
    assert mock_run.call_args[1]["message_history"] == []
    assert mock_run.call_args[1]["deferred_tool_results"] is None
    assert mock_run.call_args[1]["usage_limits"] is not None


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
    manager.add_hook(record, events=[HookEvent.STOP])

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

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
async def test_stop_event_data_carries_turn_slice_and_wrote_files_flag():
    """The Stop hook's event_data exposes this turn's own messages, plus a
    free (no-LLM) `wrote_files` gate, so an evidence-gated hook (e.g. a
    journal-compliance agent hook) can act only on turns that actually
    touched a file."""
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

    # A dangling ToolCallPart (no matching return) is stripped by
    # sanitize_history's orphan-call cleanup, so the return is included here —
    # a call/return pair is what a genuinely completed turn looks like.
    turn_messages = [
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="Write", args={"path": "x"}, tool_call_id="1"),
            ]
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Write", content="ok", tool_call_id="1")]
        ),
        ModelResponse(parts=[TextPart(content="done")]),
    ]

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = turn_messages

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert len(captured) == 1
    assert len(captured[0]["turn"]) == len(turn_messages)
    assert captured[0]["wrote_files"] is True


@pytest.mark.asyncio
async def test_stop_event_data_wrote_files_false_for_read_only_turn():
    """A turn that only calls a read-only tool does not set `wrote_files`."""
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

    turn_messages = [
        ModelResponse(
            parts=[ToolCallPart(tool_name="Read", args={"path": "x"}, tool_call_id="1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="Read", content="contents", tool_call_id="1")
            ]
        ),
        ModelResponse(parts=[TextPart(content="done")]),
    ]

    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "done"
    mock_result.all_messages.return_value = turn_messages

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=mock_result)

    agent.run = _run_from(_gen)

    await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert captured[0]["wrote_files"] is False


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

    agent.run = _run_from(_gen)

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
    manager.add_hook(OnceHook(), events=[HookEvent.STOP])

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

    agent.run = _run_from(_gen)

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
    manager.add_hook(OnceHook(), events=[HookEvent.STOP])

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

    agent.run = _run_from(_gen)
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
    manager.add_hook(rec, events=[HookEvent.SESSION_START])

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
    manager.add_hook(rec, events=[HookEvent.USER_PROMPT_SUBMIT])

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
    manager.add_hook(rec, events=[HookEvent.PRE_COMPACT])

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
    manager.add_hook(rec, events=[HookEvent.POST_COMPACT])

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
    manager.add_hook(rec, events=[HookEvent.STOP_FAILURE])

    agent = MagicMock()

    async def _gen(*args, **kwargs):
        raise ValueError("bad request")
        yield  # pragma: no cover — marks this a generator

    agent.run = _run_from(_gen)

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
    agent.run = MagicMock(
        side_effect=AssertionError("model must not run when prompt is blocked")
    )

    async def blocking_hook(context: HookContext) -> HookResult:
        if context.event == HookEvent.USER_PROMPT_SUBMIT:
            return HookResult.block("policy violation")
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(blocking_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

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

    agent.run = _run_from(_gen)

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
    manager.add_hook(BlockOnce(), events=[HookEvent.STOP])

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

    agent.run = _run_from(_gen)

    async def always_block(context: HookContext) -> HookResult:
        if context.event == HookEvent.STOP:
            return HookResult(
                success=False,
                should_stop=True,
                modifications={"decision": "block", "reason": "more"},
            )
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(always_block, events=[HookEvent.STOP])

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

    agent.run = _run_from(_gen)

    manager = HookManager(search_dirs=[])

    async def session_start_hook(ctx):
        return HookResult(
            success=True, modifications={"additionalContext": "INIT_CONTEXT"}
        )

    manager.add_hook(session_start_hook, events=[HookEvent.SESSION_START])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h
    limiter.acquire = AsyncMock()

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)

        result, _ = await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            hook_manager=manager,
        )

        # Check history passed to agent.run
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

    agent.run = _run_from(_gen)

    manager = HookManager(search_dirs=[])

    async def prompt_hook(ctx):
        return HookResult(
            success=True, modifications={"additionalContext": "PROMPT_CONTEXT"}
        )

    manager.add_hook(prompt_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    limiter = MagicMock(spec=LLMLimiter)
    limiter.count_tokens.return_value = 10
    limiter.max_token_per_request = 1000
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h
    limiter.acquire = AsyncMock()

    with patch.object(agent, "run") as mock_run:
        mock_run.side_effect = _run_from(_gen)

        result, _ = await run_agent(
            agent=agent,
            message="Hi",
            message_history=[],
            limiter=limiter,
            hook_manager=manager,
        )

        # Check message passed to agent.run
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

    agent.run = _run_from(_gen)

    ui1 = MagicMock()
    ui2 = MagicMock()

    limiter = MagicMock(spec=LLMLimiter)
    limiter.acquire = AsyncMock()
    limiter.max_token_per_request = 1000
    limiter.count_tokens.return_value = 10
    limiter.fit_context_window.side_effect = lambda h, m, r, *args, **kwargs: h

    # MultiUI is imported (real, module-level) into agent/run/setup.py, which
    # is where resolve_context_dependencies actually looks it up — patch
    # there, not at zrb.llm.ui.multi_ui, since setup.py's own name binding
    # predates this patch.
    with patch(
        "zrb.llm.agent.run.setup.MultiUI", return_value=MagicMock()
    ) as mock_multi:
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


# ── Per-run request budget ───────────────────────────────────────────────
# A run used to pass `request_limit=None`, so nothing could stop a model that
# had stopped converging. The worst observed case re-edited the same nine files
# from memory for 343 tool calls and only ended when the wall clock did. The
# prompt's Recovery rules tell the model to change approach by the third
# attempt; this is the half of that rule something can actually enforce.


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
