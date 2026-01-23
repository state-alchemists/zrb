from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import ToolApproved

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session


@pytest.mark.asyncio
async def test_llm_task_tool_confirmation_called():
    # Mock create_agent and run_agent in the module where LLMTask is defined
    with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:

        mock_create_agent.return_value = "mock_agent"
        mock_run_agent.return_value = ("Done", [])

        def tool_confirmation(call):
            return ToolApproved()

        task = LLMTask(
            name="test-task",
            message="Hello",
            tool_confirmation=tool_confirmation,
            yolo=False,
        )

        shared_ctx = SharedContext()
        session = Session(shared_ctx)

        # Execute
        await task.async_run(session)

        # Assert
        mock_run_agent.assert_called_once()
        args, kwargs = mock_run_agent.call_args
        assert kwargs["tool_confirmation"] == tool_confirmation


@pytest.mark.asyncio
async def test_llm_chat_task_tool_confirmation_forwarded():
    from zrb.llm.task.llm_chat_task import LLMChatTask

    def tool_confirmation(call):
        return ToolApproved()

    chat_task = LLMChatTask(
        name="chat-task",
        tool_confirmation=tool_confirmation,
        interactive=False,  # So we use the core task
    )

    # We want to check if the core task has the tool_confirmation
    core_task = chat_task._create_llm_task_core([])
    assert core_task._tool_confirmation == tool_confirmation
