from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import BinaryContent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserContent,
    UserPromptPart,
)

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session


@pytest.mark.asyncio
async def test_llm_task_retry_logic():
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

    task = LLMTask(
        name="test-task",
        message="Hello",
        retries=1,
        history_manager=mock_history_manager,
    )

    with patch("zrb.llm.task.llm_task.run_agent") as mock_run_agent:
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

        await task.exec(session)

        assert mock_run_agent.call_count == 2

        second_call_kwargs = mock_run_agent.call_args_list[1].kwargs
        assert "[SYSTEM] This is retry attempt 2" in second_call_kwargs.get(
            "message", ""
        )

        # The dangling tool call was closed before the retry.
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
    """A retry keeps the attachments and detects the multimodal user turn."""
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

    mock_attachment = BinaryContent(data=b"fake_image_data", media_type="image/png")
    attachments: list[UserContent] = [mock_attachment]

    task = LLMTask(
        name="test-task",
        message="What's in this image?",
        retries=1,
        history_manager=mock_history_manager,
        attachment=attachments,
    )

    with patch("zrb.llm.task.llm_task.run_agent") as mock_run_agent:
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

        await task.exec(session)

        assert mock_run_agent.call_count == 2

        second_call_kwargs = mock_run_agent.call_args_list[1].kwargs
        retry_attachments = second_call_kwargs.get("attachments", None)

        assert retry_attachments is not None, "Attachments were discarded on retry"
        assert (
            retry_attachments == attachments
        ), f"Expected attachments {attachments}, got {retry_attachments}"

        retry_message = second_call_kwargs.get("message", "")
        assert "[SYSTEM] This is retry attempt 2" in retry_message


@pytest.mark.asyncio
async def test_llm_task_detects_multimodal_content_in_history():
    """A user turn whose content is a list (text + binary) still matches on retry."""
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

        second_call_kwargs = mock_run_agent.call_args_list[1].kwargs
        retry_message = second_call_kwargs.get("message", "")

        assert (
            "[SYSTEM] This is retry attempt 2" in retry_message
        ), "Multimodal content not detected in history"


@pytest.mark.asyncio
async def test_a_permanent_error_is_not_retried_even_with_retries_allowed():
    """`LLMTask` defaults `retry_if` to `retry_unless_permanent`."""
    # Arrange
    from unittest.mock import AsyncMock

    from pydantic_ai.exceptions import UserError

    task = LLMTask(name="permanent", retries=2)
    session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
    # Act
    with (
        patch("zrb.llm.task.llm_task.create_agent"),
        patch("zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock) as run_agent,
    ):
        run_agent.side_effect = UserError("Set the `OPENAI_API_KEY` env var")
        with pytest.raises(UserError):
            await task.async_run(session)
    # Assert
    assert run_agent.call_count == 1


@pytest.mark.asyncio
async def test_an_explicit_retry_if_wins_over_the_permanent_error_default():
    # Arrange
    from unittest.mock import AsyncMock

    from pydantic_ai.exceptions import UserError

    task = LLMTask(name="always-retry", retries=1, retry_if=lambda _: True)
    session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
    # Act
    with (
        patch("zrb.llm.task.llm_task.create_agent"),
        patch("zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock) as run_agent,
    ):
        run_agent.side_effect = UserError("Set the `OPENAI_API_KEY` env var")
        with pytest.raises(UserError):
            await task.async_run(session)
    # Assert
    assert run_agent.call_count == 2
