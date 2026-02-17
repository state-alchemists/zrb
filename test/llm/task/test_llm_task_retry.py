from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session


@pytest.mark.asyncio
async def test_llm_task_retry_logic():
    # Setup
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx, state_logger=MagicMock())

    # Mock history manager to actually "store" history in memory
    mock_history_manager = MagicMock()
    stored_history = []

    def load_side_effect(name):
        return stored_history

    def update_side_effect(name, history):
        nonlocal stored_history
        stored_history = history

    mock_history_manager.load.side_effect = load_side_effect
    mock_history_manager.update.side_effect = update_side_effect

    # Pass history_manager via constructor
    task = LLMTask(
        name="test-task",
        message="Hello",
        retries=1,
        history_manager=mock_history_manager,
    )

    # Mock run_agent to fail on first attempt and succeed on second
    with patch("zrb.llm.task.llm_task.run_agent") as mock_run_agent:
        # First attempt fails with zrb_history
        failed_history = [
            ModelRequest(parts=[UserPromptPart(content="Hello")]),
            ModelResponse(
                parts=[
                    ToolCallPart(tool_name="test_tool", args={}, tool_call_id="call_1")
                ]
            ),
        ]
        error = Exception("Tool failed")
        error.zrb_history = failed_history

        mock_run_agent.side_effect = [
            error,
            (
                "Success",
                failed_history
                + [ModelRequest(parts=[UserPromptPart(content="Retry notice")])],
            ),
        ]

        # Execute publicly
        await task.exec(session)

        # Verify run_agent was called twice
        assert mock_run_agent.call_count == 2

        # Verify run_agent was called with retry notice on second attempt
        second_call_kwargs = mock_run_agent.call_args_list[1].kwargs
        assert "[System] This is retry attempt 2" in second_call_kwargs.get(
            "message", ""
        )

        # Verify ToolReturnPart was added to history before second attempt
        second_call_history = mock_run_agent.call_args_list[1].kwargs.get(
            "message_history", []
        )
        assert len(second_call_history) == 4

        from pydantic_ai.messages import ToolReturnPart

        has_tool_return = any(
            isinstance(p, ToolReturnPart)
            and "Error: Tool failed" in str(getattr(p, "content", ""))
            for msg in second_call_history
            for p in getattr(msg, "parts", [])
        )
        assert has_tool_return
