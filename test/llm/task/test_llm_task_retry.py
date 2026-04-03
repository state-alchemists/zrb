from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import BinaryContent
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


@pytest.mark.asyncio
async def test_llm_task_retry_preserves_attachments_multimodal():
    """Test that attachments are preserved on retry when user message has multimodal content.

    This tests the fix for:
    - Bug 1: Attachments being discarded on retry (returning None)
    - Bug 2: String comparison failing for multimodal content (list vs string)
    """
    # Setup
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx, state_logger=MagicMock())

    # Mock history manager
    mock_history_manager = MagicMock()
    stored_history = []

    def load_side_effect(name):
        return stored_history

    def update_side_effect(name, history):
        nonlocal stored_history
        stored_history = history

    mock_history_manager.load.side_effect = load_side_effect
    mock_history_manager.update.side_effect = update_side_effect

    # Create a mock BinaryContent attachment
    mock_attachment = BinaryContent(data=b"fake_image_data", media_type="image/png")
    attachments = [mock_attachment]

    # IMPORTANT: Pass attachment via task's attachment parameter (like LLMChatTask does)
    task = LLMTask(
        name="test-task",
        message="What's in this image?",
        retries=1,
        history_manager=mock_history_manager,
        attachment=attachments,  # Pass attachments via task parameter
    )

    with patch("zrb.llm.task.llm_task.run_agent") as mock_run_agent:
        # First attempt fails - history contains multimodal UserPromptPart
        # (content is a list: [text, BinaryContent])
        failed_history = [
            ModelRequest(
                parts=[
                    UserPromptPart(content=["What's in this image?", mock_attachment])
                ]
            ),
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

        # CRITICAL: Verify attachments are preserved on retry (Bug 1 fix)
        second_call_kwargs = mock_run_agent.call_args_list[1].kwargs
        retry_attachments = second_call_kwargs.get("attachments", None)

        # Attachments should NOT be None on retry
        assert (
            retry_attachments is not None
        ), "Attachments were discarded on retry - Bug 1 NOT FIXED"
        assert (
            retry_attachments == attachments
        ), f"Expected attachments {attachments}, got {retry_attachments}"

        # Verify retry message is sent (not original message)
        retry_message = second_call_kwargs.get("message", "")
        assert "[System] This is retry attempt 2" in retry_message


@pytest.mark.asyncio
async def test_llm_task_detects_multimodal_content_in_history():
    """Test that multimodal content in history is properly detected for retry comparison.

    This tests Bug 2: String comparison failing because part.content is a list,
    not a string, when multimodal content is present.
    """
    # Setup
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx, state_logger=MagicMock())

    mock_history_manager = MagicMock()
    stored_history = []

    def load_side_effect(name):
        return stored_history

    def update_side_effect(name, history):
        nonlocal stored_history
        stored_history = history

    mock_history_manager.load.side_effect = load_side_effect
    mock_history_manager.update.side_effect = update_side_effect

    mock_attachment = BinaryContent(data=b"test_image", media_type="image/png")
    user_message = "Analyze this"
    attachments = [mock_attachment]

    task = LLMTask(
        name="test-task",
        message=user_message,
        retries=1,
        history_manager=mock_history_manager,
    )

    with patch("zrb.llm.task.llm_task.run_agent") as mock_run_agent:
        # History contains multimodal UserPromptPart (content is a LIST, not string)
        failed_history = [
            ModelRequest(
                parts=[UserPromptPart(content=[user_message, mock_attachment])]
            ),
            ModelResponse(
                parts=[
                    ToolCallPart(tool_name="analyze", args={}, tool_call_id="call_1")
                ]
            ),
        ]
        error = Exception("Failed")
        error.zrb_history = failed_history

        mock_run_agent.side_effect = [
            error,
            ("Success", failed_history),
        ]

        await task.exec(session)

        # Verify second call detected the user message in multimodal history
        second_call_kwargs = mock_run_agent.call_args_list[1].kwargs
        retry_message = second_call_kwargs.get("message", "")

        # If Bug 2 is not fixed, it would send original message instead of retry notice
        # because str(["Analyze this", BinaryContent]) != "Analyze this"
        assert (
            "[System] This is retry attempt 2" in retry_message
        ), "Multimodal content not detected in history - Bug 2 NOT FIXED"
