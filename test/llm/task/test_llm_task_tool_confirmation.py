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

        mock_history_manager = patch(
            "zrb.llm.history_manager.any_history_manager.AnyHistoryManager"
        ).start()
        mock_history_manager.load.return_value = []

        task = LLMTask(
            name="test-task",
            message="Hello",
            tool_confirmation=tool_confirmation,
            history_manager=mock_history_manager,
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
