from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import (
    BufferedUI,
    IndentedUI,
    create_delegate_to_agent_tool,
    create_parallel_delegate_tool,
)


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


# BufferedUI Tests
def test_buffered_ui_append_to_output():
    """Test BufferedUI buffers output correctly."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Line 1")
    ui.append_to_output("Line 2")

    # Output should be buffered, not written yet
    # append_to_output adds end="\n" by default, so we get "Line 1\n" and "Line 2\n"
    buffered = ui.get_buffered_output()
    assert "Line 1" in buffered
    assert "Line 2" in buffered
    # Nothing should be written to wrapped UI yet
    assert mock_wrapped.append_to_output.call_count == 0


def test_buffered_ui_flush_to_parent():
    """Test BufferedUI flush_to_parent with prefix."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Line 1\nLine 2")
    ui.flush_to_parent()

    # Should have called append_to_output with prefixed content
    assert mock_wrapped.append_to_output.call_count == 1
    # Check that the call contains the prefixed lines
    call_arg = mock_wrapped.append_to_output.call_args[0][0]
    assert "[AGENT]" in call_arg


def test_buffered_ui_clear_buffer():
    """Test BufferedUI clear_buffer clears output."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Some content")
    assert "Some content" in ui.get_buffered_output()

    ui.clear_buffer()
    assert ui.get_buffered_output() == ""


@pytest.mark.asyncio
async def test_buffered_ui_ask_user():
    """Test BufferedUI ask_user forwards to parent with prefix."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="user response")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    result = await ui.ask_user("What should I do?")

    assert result == "user response"
    mock_wrapped.ask_user.assert_called_once()
    # Check prefix was added
    call_arg = mock_wrapped.ask_user.call_args[0][0]
    assert "[AGENT]" in call_arg
    assert "What should I do?" in call_arg


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_no_prefix():
    """Test BufferedUI ask_user without prefix."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="response")
    ui = BufferedUI(mock_wrapped, prefix="")

    result = await ui.ask_user("Question?")

    assert result == "response"
    # No prefix should be added
    mock_wrapped.ask_user.assert_called_with("Question?")


# Parallel Delegate Tool Tests
def test_create_parallel_delegate_tool_docstring(mock_sub_agent_manager):
    """Test parallel delegate tool has proper docstring."""
    tool = create_parallel_delegate_tool(mock_sub_agent_manager)
    assert "test-agent" in tool.__doc__
    assert "A test agent" in tool.__doc__
    assert "parallel" in tool.__doc__.lower()
    assert "DelegateToAgentsParallel" == tool.__name__


@pytest.mark.asyncio
async def test_parallel_delegate_empty_tasks(mock_sub_agent_manager):
    """Test parallel delegate with empty task list returns early."""
    tool = create_parallel_delegate_tool(mock_sub_agent_manager)

    result = await tool([])

    assert result == "No tasks provided."


@pytest.mark.asyncio
async def test_parallel_delegate_single_task(mock_sub_agent_manager):
    """Test parallel delegate with single task."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_parallel_delegate_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Task result", [])

        tasks = [{"agent_name": "test-agent", "task": "do something"}]
        result = await tool(tasks)

        assert "Sub-agent 'test-agent' completed" in result
        assert "Task result" in result


@pytest.mark.asyncio
async def test_parallel_delegate_multiple_tasks(mock_sub_agent_manager):
    """Test parallel delegate with multiple tasks."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_parallel_delegate_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Result", [])

        tasks = [
            {"agent_name": "test-agent", "task": "task 1"},
            {"agent_name": "test-agent", "task": "task 2"},
        ]
        result = await tool(tasks)

        # Should call run_agent twice (in parallel via gather)
        assert mock_run_agent.call_count == 2
        assert "Sub-agent 'test-agent' completed" in result


@pytest.mark.asyncio
async def test_parallel_delegate_with_additional_context(mock_sub_agent_manager):
    """Test parallel delegate passes additional_context if provided."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_parallel_delegate_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Result", [])

        tasks = [
            {"agent_name": "test-agent", "task": "task", "additional_context": "extra"}
        ]
        await tool(tasks)

        # Check that additional_context was included in message
        call_kwargs = mock_run_agent.call_args.kwargs
        assert "extra" in call_kwargs["message"]


@pytest.mark.asyncio
async def test_parallel_delegate_agent_not_found(mock_sub_agent_manager):
    """Test parallel delegate when agent is not found."""
    mock_sub_agent_manager.create_agent.return_value = None

    tool = create_parallel_delegate_tool(mock_sub_agent_manager)

    tasks = [{"agent_name": "missing-agent", "task": "task"}]
    result = await tool(tasks)

    assert "Sub-agent 'missing-agent' failed" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_parallel_delegate_with_exception(mock_sub_agent_manager):
    """Test parallel delegate handles exceptions gracefully."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_parallel_delegate_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", side_effect=Exception("Agent failed")
    ):
        tasks = [{"agent_name": "test-agent", "task": "task"}]
        result = await tool(tasks)

        assert "Sub-agent 'test-agent' failed" in result
        assert "Agent failed" in result


@pytest.mark.asyncio
async def test_parallel_delegate_mixed_success_failure(mock_sub_agent_manager):
    """Test parallel delegate with mixed success and failure."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_parallel_delegate_tool(mock_sub_agent_manager)
    call_count = [0]

    async def side_effect_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return ("Success", [])
        else:
            raise Exception("Agent error")

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.side_effect = side_effect_run

        tasks = [
            {"agent_name": "test-agent", "task": "task1"},
            {"agent_name": "test-agent", "task": "task2"},
        ]
        result = await tool(tasks)

        # Should have both results
        assert "completed" in result
        assert "failed" in result
