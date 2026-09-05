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
async def test_isolate_worktree_enters_and_cleans_up_when_clean(mock_sub_agent_manager):
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
        mock_run_agent.return_value = ("done", [])
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

    mock_enter.assert_awaited_once()
    mock_exit.assert_awaited_once_with("/repo/.zrb/worktree/x")
    assert "done" in result
    assert "Worktree left in place" not in result


@pytest.mark.asyncio
async def test_isolate_worktree_leaves_dirty_worktree_and_reports_path(
    mock_sub_agent_manager,
):
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
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=True,
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
        mock_run_agent.return_value = ("done", [])
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

    mock_exit.assert_not_called()
    assert "Worktree left in place for review: /repo/.zrb/worktree/x" in result


@pytest.mark.asyncio
async def test_isolate_worktree_leaves_worktree_with_new_commits_and_keeps_branch(
    mock_sub_agent_manager,
):
    """A worktree with no uncommitted diff but commits beyond its fork point
    must be left in place too — a clean `git status` alone must never be
    treated as "safe to force-delete the branch" (the branch may hold a
    sub-agent's committed deliverable)."""
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
            return_value=True,
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        mock_run_agent.return_value = ("done", [])
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

    mock_exit.assert_not_called()
    assert "Worktree left in place for review: /repo/.zrb/worktree/x" in result
