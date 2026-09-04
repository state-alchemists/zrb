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
async def test_delegate_fan_out_cap_disabled_by_zero(
    mock_sub_agent_manager, monkeypatch
):
    """0 disables the cap, matching LLM_MAX_REQUEST_PER_RUN's convention —
    all tasks run concurrently, as before this fix.
    """
    monkeypatch.setenv("ZRB_LLM_MAX_PARALLEL_DELEGATIONS", "0")
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    tasks, fake_run_agent, get_max_in_flight = await _fan_out_tracking_concurrency(5)
    with patch("zrb.llm.tool.delegate.run_agent", side_effect=fake_run_agent):
        result = await tool(tasks=tasks)

    assert get_max_in_flight() == 5
    assert result.count("completed:") == 5


@pytest.mark.asyncio
async def test_delegate_non_goals_as_string(mock_sub_agent_manager):
    """A non_goals string (not a list) still renders as a single bullet."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("ok", [])
        await tool(
            agent_name="test-agent",
            deliverable="d",
            task="t",
            non_goals="do not touch prod",
        )
        message = mock_run_agent.call_args.kwargs["message"]
        assert "  - do not touch prod" in message


@pytest.mark.asyncio
async def test_delegate_envelope_includes_active_worktree(mock_sub_agent_manager):
    """When a worktree is active, the envelope CONTEXT names it alongside context."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/feat",
        ),
    ):
        mock_run_agent.return_value = ("ok", [])
        await tool(
            agent_name="test-agent",
            deliverable="d",
            task="t",
            non_goals=[],
            additional_context="existing context",
        )
        message = mock_run_agent.call_args.kwargs["message"]
        assert "Active worktree: /repo/.zrb/worktree/feat" in message
        assert "existing context" in message


@pytest.mark.asyncio
async def test_delegate_active_worktree_without_context(mock_sub_agent_manager):
    """With no additional_context, the worktree line stands alone in CONTEXT."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch("zrb.llm.tool.delegate.get_active_worktree", return_value="/wt"),
    ):
        mock_run_agent.return_value = ("ok", [])
        await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
        message = mock_run_agent.call_args.kwargs["message"]
        assert "Active worktree: /wt" in message


@pytest.mark.asyncio
async def test_delegate_recursion_error_surfaces_suggestion(mock_sub_agent_manager):
    """A RecursionError from the sub-agent maps to an actionable error string."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent",
        new_callable=AsyncMock,
        side_effect=RecursionError(),
    ):
        result = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    assert "Recursion depth exceeded" in result


@pytest.mark.asyncio
async def test_delegate_swallows_hook_manager_errors(mock_sub_agent_manager):
    """A hook manager that raises must not break delegation (fire-and-forget)."""
    from zrb.llm.agent.run.runner import current_hook_manager

    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    boom_manager = MagicMock()
    boom_manager.execute_hooks = AsyncMock(side_effect=RuntimeError("hook boom"))

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    token = current_hook_manager.set(boom_manager)
    try:
        with patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("ok", [])
            result = await tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            )
    finally:
        current_hook_manager.reset(token)

    # Delegation succeeds despite the hook manager blowing up.
    assert "completed:" in result
    assert "ok" in result
    boom_manager.execute_hooks.assert_awaited()


@pytest.mark.asyncio
async def test_fire_subagent_hook_swallows_cancelled_error():
    """`fire_subagent_hook` documents "Never raises" -- `asyncio.CancelledError`
    is a `BaseException`, not caught by a plain `except Exception`, so it must
    be caught explicitly. This call site fires from inside `run_agent_task`'s
    `finally` block (after its result is already decided) and from the top of
    its `try` block -- a stray cancel landing in either window must not
    override an already-settled return or escape uncaught."""
    from zrb.llm.agent.run.runner import current_hook_manager
    from zrb.llm.hook.types import HookEvent
    from zrb.llm.tool.delegate import fire_subagent_hook

    cancelling_manager = MagicMock()
    cancelling_manager.execute_hooks = AsyncMock(side_effect=asyncio.CancelledError())

    token = current_hook_manager.set(cancelling_manager)
    try:
        # Must not raise.
        await fire_subagent_hook(HookEvent.SUBAGENT_STOP, "test-agent", "abcd1234")
    finally:
        current_hook_manager.reset(token)

    cancelling_manager.execute_hooks.assert_awaited()


@pytest.mark.asyncio
async def test_delegate_fan_out_reports_failed_task(mock_sub_agent_manager):
    """A failing sub-agent in a fan-out surfaces as an Error line; others succeed."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.side_effect = [("Result OK", []), Exception("boom")]
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

    assert "Result OK" in result
    assert "Error: boom" in result


def test_create_delegate_tool_uses_default_manager():
    """Passing no manager falls back to the module default singleton."""
    default = MagicMock(spec=SubAgentManager)
    default.scan.return_value = []

    with patch("zrb.llm.tool.delegate.default_sub_agent_manager", default):
        tool = create_delegate_to_agent_tool()

    assert tool.__name__ == "DelegateToAgent"
    default.scan.assert_called()


@pytest.mark.asyncio
async def test_fan_out_does_not_flush_routine_output_to_main(mock_sub_agent_manager):
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    parent_ui = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    async def run_and_write_to_buffer(*args, ui=None, **kwargs):
        if ui is not None:
            ui.append_to_output("searching for things...")
        return "done", []

    with (
        patch("zrb.llm.tool.delegate.run_agent", side_effect=run_and_write_to_buffer),
        patch("zrb.llm.tool.delegate.get_current_ui", return_value=parent_ui),
    ):
        await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                }
            ]
        )

    parent_ui.append_to_output.assert_not_called()
