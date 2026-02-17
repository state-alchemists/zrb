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
    task = LLMTask(name="test-task", message="Hello", retries=0)

    # Mock history manager
    mock_history_manager = MagicMock()
    mock_history_manager.load.return_value = []
    task._history_manager = mock_history_manager

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

        # First attempt (fails)
        with pytest.raises(Exception, match="Tool failed"):
            await task.exec(session)

        # Verify history was updated and saved
        assert mock_history_manager.update.called
        updated_history = mock_history_manager.update.call_args[0][1]
        assert len(updated_history) == 4

        # Second attempt (Retry)
        # Create a new session for retry
        session2 = Session(shared_ctx=shared_ctx, state_logger=MagicMock())
        # Simulate retry state
        ctx2 = task.get_ctx(session2)
        ctx2.set_attempt(2)
        mock_history_manager.load.return_value = updated_history
        
        await task.exec(session2)

        # Verify run_agent was called with retry notice
        # Check all calls to run_agent
        found_retry_notice = False
        for call_args in mock_run_agent.call_args_list:
            # Check positional and keyword arguments
            args, kwargs = call_args
            msg = kwargs.get("message", "")
            if "[System] This is retry attempt 2" in msg:
                found_retry_notice = True
                break
        
        if not found_retry_notice:
            # Print for debugging if it fails
            print(f"Calls: {mock_run_agent.call_args_list}")
            
        assert found_retry_notice
