import pytest
from unittest.mock import MagicMock, patch
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session
from zrb.context.shared_context import SharedContext
from pydantic_ai.messages import ModelRequest, UserPromptPart, ModelResponse, ToolCallPart
import asyncio

@pytest.mark.asyncio
async def test_llm_task_retry_logic():
    # Setup
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    task = LLMTask(name="test-task", message="Hello")
    ctx = task.get_ctx(session)
    ctx.set_attempt(1)

    # Mock history manager
    mock_history_manager = MagicMock()
    mock_history_manager.load.return_value = []
    task._history_manager = mock_history_manager

    # Mock run_agent to fail on first attempt and succeed on second
    with patch("zrb.llm.task.llm_task.run_agent") as mock_run_agent:
        # First attempt fails with zrb_history
        failed_history = [
            ModelRequest(parts=[UserPromptPart(content="Hello")]),
            ModelResponse(parts=[ToolCallPart(tool_name="test_tool", args={}, tool_call_id="call_1")])
        ]
        error = Exception("Tool failed")
        error.zrb_history = failed_history
        
        mock_run_agent.side_effect = [
            error,
            ("Success", failed_history + [ModelRequest(parts=[UserPromptPart(content="Retry notice")])])
        ]

        # First attempt
        with pytest.raises(Exception) as excinfo:
            await task._exec_action(ctx)
        assert str(excinfo.value) == "Tool failed"

        # Verify history was updated and saved
        assert mock_history_manager.update.called
        assert mock_history_manager.save.called
        
        # Check what was saved (it should have ToolReturnPart and Error message)
        updated_history = mock_history_manager.update.call_args[0][1]
        # UserPrompt, ModelResponse(ToolCall), ToolReturn, Error
        assert len(updated_history) == 4 
        
        # Verify specific parts in the updated history
        from pydantic_ai.messages import ToolReturnPart
        has_tool_return = any(isinstance(p, ToolReturnPart) and "Error: Tool failed" in str(getattr(p, 'content', '')) for msg in updated_history for p in getattr(msg, 'parts', []))
        has_error_msg = any("[System] Error occurred: Tool failed" in str(getattr(p, 'content', '')) for msg in updated_history for p in getattr(msg, 'parts', []))
        
        assert has_tool_return
        assert has_error_msg

        # Second attempt (Retry)
        ctx.set_attempt(2)
        mock_history_manager.load.return_value = updated_history
        
        await task._exec_action(ctx)
        
        # Verify run_agent was called with retry notice
        second_call_args = mock_run_agent.call_args_list[1]
        assert "[System] This is retry attempt 2" in second_call_args.kwargs["message"]
        assert second_call_args.kwargs["attachments"] is None
