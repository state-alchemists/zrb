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
