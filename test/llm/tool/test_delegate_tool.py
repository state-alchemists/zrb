from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import IndentedUI, create_delegate_to_agent_tool


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


def test_create_delegate_tool_docstring(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    assert "test-agent" in tool.__doc__
    assert "A test agent" in tool.__doc__


@pytest.mark.asyncio
async def test_delegate_tool_agent_not_found(mock_sub_agent_manager):
    mock_sub_agent_manager.create_agent.return_value = None
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with pytest.raises(ValueError, match="Sub-agent 'non-existent' not found."):
        await tool("non-existent", "task")


@pytest.mark.asyncio
async def test_delegate_tool_success(mock_sub_agent_manager):
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Agent Result", [])

        result = await tool("test-agent", "do this", "context")

        assert "Sub-agent 'test-agent' completed the task" in result
        assert "Agent Result" in result

        # Verify call arguments
        mock_run_agent.assert_called_once()
        call_kwargs = mock_run_agent.call_args.kwargs
        assert call_kwargs["agent"] == mock_agent
        assert "do this" in call_kwargs["message"]
        assert "context" in call_kwargs["message"]
        assert isinstance(call_kwargs["ui"], IndentedUI)


@pytest.mark.asyncio
async def test_delegate_tool_exception(mock_sub_agent_manager):
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch("zrb.llm.tool.delegate.run_agent", side_effect=Exception("Run failed")):
        result = await tool("test-agent", "task")
        assert "Error executing sub-agent 'test-agent': Run failed" in result


# IndentedUI Tests
@pytest.mark.asyncio
async def test_indented_ui():
    mock_wrapped = MagicMock()
    # ask_user is async
    mock_wrapped.ask_user = AsyncMock()

    ui = IndentedUI(mock_wrapped, indent=">> ")

    # Test ask_user
    await ui.ask_user("Question")
    mock_wrapped.ask_user.assert_called_with(">> Question")

    # Test append_to_output
    ui.append_to_output("Line 1\nLine 2")
    # First time adds newline
    assert mock_wrapped.append_to_output.call_count == 2
    # Verify content logic (simplified check)
