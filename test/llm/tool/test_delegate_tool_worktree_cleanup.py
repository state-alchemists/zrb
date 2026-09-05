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


@pytest.mark.asyncio
async def test_isolate_worktree_cleanup_failure_reported_not_raised(
    mock_sub_agent_manager,
):
    """A cleanup failure (e.g. `worktree_has_new_commits` raising) must not
    escape `asyncio.gather` and abort the whole fan-out — it's reported on
    the task's own result instead."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch("zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock),
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            side_effect=RuntimeError("git binary missing"),
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "agent-a",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                },
                {
                    "agent_name": "agent-b",
                    "deliverable": "d2",
                    "task": "t2",
                    "non_goals": [],
                },
            ]
        )

    # The failing task's cleanup note is reported, not raised — and its
    # sibling (no isolate_worktree, unaffected) still completes normally.
    assert "Worktree cleanup failed" in result
    assert "git binary missing" in result
    assert "agent-b" in result and "done" in result


@pytest.mark.asyncio
async def test_isolate_worktree_cleans_up_even_when_subagent_errors(
    mock_sub_agent_manager,
):
    """Cleanup must survive a crashed/erroring sub-agent (ADR-0068)."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_exit.assert_awaited_once_with("/repo/.zrb/worktree/x")
    assert "Error: boom" in result


@pytest.mark.asyncio
async def test_fan_out_without_isolate_worktree_skips_worktree_calls(
    mock_sub_agent_manager,
):
    """Default (no isolate_worktree) must not touch worktrees at all."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
    ):
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                }
            ]
        )

    mock_enter.assert_not_called()
    mock_exit.assert_not_called()
    assert "done" in result


@pytest.mark.asyncio
async def test_isolate_worktree_enter_failure_skips_subagent(mock_sub_agent_manager):
    """A failed EnterWorktree must not run the sub-agent at all."""
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree",
            new_callable=AsyncMock,
            return_value="Error: Not inside a git repository.",
        ),
        patch("zrb.llm.tool.delegate.get_active_worktree", return_value=""),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
    ):
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_run_agent.assert_not_called()
    assert "Not inside a git repository" in result
