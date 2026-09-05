import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import BufferedUI, create_delegate_to_agent_tool


@pytest.fixture
def mock_sub_agent_manager():
    manager = MagicMock(spec=SubAgentManager)
    # Setup scan return value
    agent_def = SubAgentDefinition(
        name="test-agent",
        path="path",
        description="A test agent",
        system_prompt="prompt",
    )
    manager.scan.return_value = [agent_def]
    return manager


@pytest.mark.asyncio
async def test_delegate_tool_success(mock_sub_agent_manager):
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Agent Result", [])

        result = await tool(
            agent_name="test-agent",
            deliverable="updated foo.py",
            task="do this",
            non_goals=["do not refactor unrelated code"],
            additional_context="context",
        )

        assert "test-agent" in result
        assert "completed:" in result
        assert "Agent Result" in result

        # Verify call arguments
        mock_run_agent.assert_called_once()
        call_kwargs = mock_run_agent.call_args.kwargs
        assert call_kwargs["agent"] == mock_agent
        message = call_kwargs["message"]
        # Envelope must fence the sub-agent before any free-form prose
        assert "DELIVERABLE: updated foo.py" in message
        assert "NON-GOALS" in message
        assert "do not refactor unrelated code" in message
        assert "do this" in message
        assert "context" in message
        assert "BEFORE RETURNING" in message
        assert isinstance(call_kwargs["ui"], BufferedUI)


@pytest.mark.asyncio
async def test_delegate_passes_live_sessions_run_scope_to_run_agent(
    mock_sub_agent_manager,
):
    """The live-session registry entry's run_scope must reach run_agent, so
    a later continuation of this same sub-agent (live_session.py) can reuse
    it instead of each turn getting its own file_observation.py bucket."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()  # earlier tests may have left sessions
    try:
        mock_agent = MagicMock()
        mock_sub_agent_manager.create_agent.return_value = mock_agent

        tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

        with patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Agent Result", [])

            await tool(
                agent_name="test-agent",
                deliverable="updated foo.py",
                task="do this",
                non_goals=[],
                additional_context="",
            )

            [session] = live_subagent_session_registry.active("default")
            call_kwargs = mock_run_agent.call_args.kwargs
            assert call_kwargs["run_scope"] == session.run_scope
            assert call_kwargs["run_scope"] != ""
    finally:
        # A failed assert must not leak this session into other tests.
        live_subagent_session_registry.clear()


@pytest.mark.asyncio
async def test_delegate_fires_subagent_start_stop(mock_sub_agent_manager):
    """Delegation fires SubagentStart before and SubagentStop after the run, on
    the parent run's hook manager, with a shared agent_id and agent_type=name."""
    from zrb.llm.agent.run.runner import current_hook_manager
    from zrb.llm.hook.interface import HookContext, HookResult
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

    mock_sub_agent_manager.create_agent.return_value = MagicMock()

    events: list = []

    async def rec(context: HookContext) -> HookResult:
        events.append((context.event, context.agent_type, context.agent_id))
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(rec, events=[HookEvent.SUBAGENT_START, HookEvent.SUBAGENT_STOP])

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    token = current_hook_manager.set(manager)
    try:
        with patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("ok", [])
            await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
    finally:
        current_hook_manager.reset(token)

    assert events[0][0] == HookEvent.SUBAGENT_START
    assert events[-1][0] == HookEvent.SUBAGENT_STOP
    # agent_type is the delegated name; start and stop share one agent_id.
    assert all(agent_type == "test-agent" for (_e, agent_type, _id) in events)
    assert len({agent_id for (_e, _t, agent_id) in events}) == 1


@pytest.mark.asyncio
async def test_delegate_tool_empty_non_goals_renders_none_declared(
    mock_sub_agent_manager,
):
    """Empty non_goals list still produces a visible placeholder in the envelope."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("ok", [])
        await tool(
            agent_name="test-agent",
            deliverable="d",
            task="t",
            non_goals=[],
        )
        message = mock_run_agent.call_args.kwargs["message"]
        assert "(none declared)" in message


@pytest.mark.asyncio
async def test_delegate_tool_exception(mock_sub_agent_manager):
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch("zrb.llm.tool.delegate.run_agent", side_effect=Exception("Run failed")):
        result = await tool(
            agent_name="test-agent",
            deliverable="d",
            task="task",
            non_goals=[],
        )
        assert "Error:" in result
        assert "Run failed" in result


@pytest.mark.asyncio
async def test_delegate_human_cancel_returns_gracefully(mock_sub_agent_manager):
    """Esc while viewing a running sub-agent (TUI) cancels only that sub-agent:
    the delegate swallows the human-flagged CancelledError and reports a
    cancelled result, so a main agent awaiting the delegation (e.g. a fan-out's
    `asyncio.gather`) is NOT itself cancelled."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()  # earlier tests may have left sessions
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()  # never finishes on its own

    try:
        with patch("zrb.llm.tool.delegate.run_agent", side_effect=blocking_run_agent):
            run_task = asyncio.create_task(
                tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
            )
            await started.wait()
            [session] = live_subagent_session_registry.active("default")
            # The task driving the delegation is registered as the session's
            # active task; cancelling through the registry is exactly what the
            # TUI's Esc does.
            assert session.active_task is run_task
            assert live_subagent_session_registry.cancel("default", session.agent_id)
            result = await run_task  # completes instead of raising CancelledError
    finally:
        live_subagent_session_registry.clear()

    assert "Cancelled by user" in result
