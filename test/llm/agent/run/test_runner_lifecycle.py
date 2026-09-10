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
