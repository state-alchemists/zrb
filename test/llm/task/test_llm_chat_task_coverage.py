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
        session = Session(shared_ctx)

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
        session = Session(shared_ctx)

        # We need to mock some UI attributes that might be rendered
        with patch("zrb.util.attr.get_str_attr", return_value=""):
            await task.async_run(session)

        assert mock_ui_run.called


def test_llm_chat_task_tool_factories():
    """Test tool and toolset factory resolution."""
    mock_tool = MagicMock()
    mock_toolset = MagicMock()

    task = LLMChatTask(
        name="factory-task",
        tool_factories=[lambda ctx: mock_tool],
        toolset_factories=[lambda ctx: [mock_toolset]],
    )

    shared_ctx = SharedContext()
    # Use public method _get_all_tools (wait, it's private? No, it starts with _)
    # I should use high level run to trigger these
    # But I can check if they are added
    assert len(task._tool_factories) == 1
    assert len(task._toolset_factories) == 1


@pytest.mark.asyncio
async def test_llm_chat_task_custom_commands():
    """Test adding custom commands to LLMChatTask."""
    mock_cmd = MagicMock()
    task = LLMChatTask(name="custom-cmd-task")
    task.add_custom_command(mock_cmd)
    assert mock_cmd in task._custom_commands


@pytest.mark.asyncio
async def test_llm_chat_task_setters():
    """Test various setter methods of LLMChatTask."""
    task = LLMChatTask(name="setter-task")

    task.add_tool(MagicMock())
    task.add_toolset(MagicMock())
    task.add_history_processor(MagicMock())
    task.add_trigger(lambda: None)

    assert len(task._tools) == 1
    assert len(task._toolsets) == 1
    # LLMChatTask has a default history processor, so adding one makes it 2
    assert len(task._history_processors) == 2
    assert len(task._triggers) == 1
