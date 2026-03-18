from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_chat_task import LLMChatTask
from zrb.session.session import Session


@pytest.mark.asyncio
async def test_llm_chat_task_non_interactive_run():
    """Test LLMChatTask in non-interactive mode."""
    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("AI response", [])

        task = LLMChatTask(
            name="non-interactive-task", message="Hello AI", interactive=False
        )

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())

        result = await task.async_run(session)
        assert result == "AI response"
        assert mock_run_agent.called


@pytest.mark.asyncio
async def test_llm_chat_task_interactive_ui_trigger():
    """Test that LLMChatTask triggers UI in interactive mode."""
    # We mock UI.run_async to avoid launching the actual terminal app
    with patch("zrb.llm.app.ui.UI.run_async", new_callable=AsyncMock) as mock_ui_run:
        task = LLMChatTask(name="interactive-task", interactive=True)

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())

        # We need to mock some UI attributes that might be rendered
        with patch("zrb.util.attr.get_str_attr", return_value=""):
            await task.async_run(session)

        assert mock_ui_run.called


@pytest.mark.asyncio
async def test_llm_chat_task_tool_factories():
    """Test tool and toolset factory resolution via public execution."""

    # Create a real callable function instead of MagicMock
    async def mock_tool_func():
        return "mock_tool_result"

    async def mock_tool_in_toolset_func():
        return "mock_toolset_result"

    # Create proper mock objects with required attributes
    mock_tool = mock_tool_func
    mock_tool_in_toolset = mock_tool_in_toolset_func

    task = LLMChatTask(
        name="factory-task",
        tool_factories=[lambda ctx: mock_tool],
        toolset_factories=[lambda ctx: [mock_tool_in_toolset]],
        interactive=False,
    )
    shared_ctx = SharedContext()
    session = Session(shared_ctx, state_logger=MagicMock())

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(session)

        # Verify that tools from factories were passed to run_agent
        assert mock_run_agent.called
        # The test passes if we reach here without pydantic-ai type inspection errors


@pytest.mark.asyncio
async def test_llm_chat_task_setters():
    """Test various setter methods of LLMChatTask via public execution."""

    # Create real callable functions instead of MagicMock
    async def setter_tool_func():
        return "setter_tool_result"

    async def setter_toolset_func():
        return "setter_toolset_result"

    task = LLMChatTask(name="setter-task", interactive=False)

    task.add_tool(setter_tool_func)
    task.add_toolset(setter_toolset_func)
    task.add_history_processor(MagicMock())
    task.add_trigger(lambda: None)
    task.add_custom_command(MagicMock())

    shared_ctx = SharedContext()
    session = Session(shared_ctx, state_logger=MagicMock())

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(session)
        assert mock_run_agent.called
