import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import create_delegate_to_agent_tool


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


@pytest.fixture
def two_agent_manager():
    manager = MagicMock(spec=SubAgentManager)
    manager.scan.return_value = [
        SubAgentDefinition(
            name="explorer", path="p1", description="reads code", system_prompt="x"
        ),
        SubAgentDefinition(
            name="builder", path="p2", description="writes code", system_prompt="y"
        ),
    ]
    return manager


async def _fan_out_tracking_concurrency(count: int):
    """5 identical fan-out task specs, plus an async run_agent stand-in that
    records the maximum number of concurrently in-flight calls.
    """
    tasks = [
        {"agent_name": "a", "deliverable": "d", "task": "t", "non_goals": []}
        for _ in range(count)
    ]
    in_flight = 0
    max_in_flight = 0

    async def fake_run_agent(*args, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return ("ok", [])

    return tasks, fake_run_agent, lambda: max_in_flight


@pytest.mark.asyncio
async def test_delegate_cancel_without_human_flag_propagates(mock_sub_agent_manager):
    """A cancellation NOT flagged by the sub-agent-view Esc (e.g. the main
    run's own Esc) must propagate as CancelledError — swallowing it would
    resurrect a main turn the user explicitly cancelled."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()  # earlier tests may have left sessions
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()

    try:
        with patch("zrb.llm.tool.delegate.run_agent", side_effect=blocking_run_agent):
            run_task = asyncio.create_task(
                tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
            )
            await started.wait()
            [session] = live_subagent_session_registry.active("default")
            assert session.cancelled_by_human is False  # fresh run, flag reset
            run_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await run_task
    finally:
        live_subagent_session_registry.clear()


@pytest.mark.asyncio
async def test_delegate_marks_done_in_live_view_on_success(mock_sub_agent_manager):
    """A completed delegation appends an end-of-session <Done> to the sub-agent's
    live-view transcript — after the turn went idle, so the view visibly ends."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    try:
        with (
            patch(
                "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
            patch("zrb.llm.tool.delegate.persist_subagent_history"),
        ):
            mock_run_agent.return_value = ("ok", [])
            result = await tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            )

        assert "completed:" in result
        [session] = live_subagent_session_registry.active("default")
        assert session.state == "idle"
        assert "<Done>" in session.buffered_ui.get_buffered_output()
    finally:
        live_subagent_session_registry.clear()


@pytest.mark.asyncio
async def test_delegate_cancelled_view_shows_no_done_marker(mock_sub_agent_manager):
    """A human-cancelled delegation must not end with <Done> — the TUI wrote
    <Esc> Canceled, and a <Done> on top would contradict it."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()

    try:
        with patch("zrb.llm.tool.delegate.run_agent", side_effect=blocking_run_agent):
            run_task = asyncio.create_task(
                tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
            )
            await started.wait()
            [session] = live_subagent_session_registry.active("default")
            live_subagent_session_registry.cancel("default", session.agent_id)
            result = await run_task
            assert "Cancelled by user" in result
            assert "<Done>" not in session.buffered_ui.get_buffered_output()
    finally:
        live_subagent_session_registry.clear()


def test_docstring_lists_all_agents_without_policy(two_agent_manager):
    tool = create_delegate_to_agent_tool(two_agent_manager)
    assert tool.__doc__ is not None
    assert "explorer" in tool.__doc__
    assert "builder" in tool.__doc__


def test_docstring_filters_denied_agent(two_agent_manager):
    from zrb.llm.permission import PermissionPolicy, Rule, current_permission_policy

    # Deny delegating to the "builder" agent specifically (arg_pattern on
    # agent_name), allow the rest.
    policy = PermissionPolicy(
        (
            Rule("DelegateToAgent", "deny", arg_pattern="builder"),
            Rule("*", "allow"),
        )
    )
    token = current_permission_policy.set(policy)
    try:
        tool = create_delegate_to_agent_tool(two_agent_manager)
    finally:
        current_permission_policy.reset(token)

    assert tool.__doc__ is not None
    assert "explorer" in tool.__doc__
    assert "builder" not in tool.__doc__


def test_delegate_docstring_mentions_fan_out(two_agent_manager):
    tool = create_delegate_to_agent_tool(two_agent_manager)
    assert tool.__doc__ is not None
    assert "FAN OUT" in tool.__doc__
    assert "tasks" in tool.__doc__


@pytest.mark.asyncio
async def test_delegate_missing_args_without_tasks(mock_sub_agent_manager):
    """No flat args and no tasks → actionable missing-args error."""
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    result = await tool()
    assert "missing required args" in result
    assert "tasks=" in result


@pytest.mark.asyncio
async def test_delegate_fan_out_missing_keys(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    result = await tool(tasks=[{"agent_name": "explorer"}])
    assert "missing required keys" in result


@pytest.mark.asyncio
async def test_delegate_fan_out_validates_all_tasks(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    result = await tool(
        tasks=[
            {
                "agent_name": "explorer",
                "deliverable": "x",
                "task": "y",
                "non_goals": [],
            },
            {"agent_name": "builder"},
        ]
    )
    assert "tasks[1]" in result


@pytest.mark.asyncio
async def test_delegate_fan_out_runs_all_and_combines(mock_sub_agent_manager):
    """tasks=[...] runs each sub-agent and returns their results together."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.side_effect = [("Result A", []), ("Result B", [])]
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "a",
                    "task": "ta",
                    "non_goals": [],
                },
                {
                    "agent_name": "test-agent",
                    "deliverable": "b",
                    "task": "tb",
                    "non_goals": [],
                },
            ]
        )

    assert mock_run_agent.call_count == 2
    assert "Result A" in result
    assert "Result B" in result
    assert result.count("completed:") == 2


@pytest.mark.asyncio
async def test_delegate_fan_out_respects_parallel_cap(
    mock_sub_agent_manager, monkeypatch
):
    """LLM_MAX_PARALLEL_DELEGATIONS (ADR-0068) bounds how many sub-agent runs
    are in flight at once — a model-requested `tasks` list has no other size
    limit.
    """
    monkeypatch.setenv("ZRB_LLM_MAX_PARALLEL_DELEGATIONS", "2")
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    tasks, fake_run_agent, get_max_in_flight = await _fan_out_tracking_concurrency(5)
    with patch("zrb.llm.tool.delegate.run_agent", side_effect=fake_run_agent):
        result = await tool(tasks=tasks)

    assert get_max_in_flight() <= 2
    assert result.count("completed:") == 5
