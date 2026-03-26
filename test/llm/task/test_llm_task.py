"""Tests for LLMTask class focusing on Public API and behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session


@pytest.fixture
def shared_ctx():
    return SharedContext()


@pytest.fixture
def session(shared_ctx):
    session = Session(shared_ctx=shared_ctx, state_logger=MagicMock())
    return session


class TestLLMTaskPublicAPI:
    """Test LLMTask using only public methods and verifying behavior via orchestrator mocks."""

    @pytest.mark.asyncio
    async def test_llm_task_passes_tools_to_agent(self, session):
        # Arrange
        tool = MagicMock()
        task = LLMTask(name="test-task", message="hello")
        task.add_tool(tool)

        # Act & Assert
        # We mock create_agent to see if our tool was passed to it during execution
        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:

            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

            # Verify the tool we added via public add_tool was passed to create_agent
            args, kwargs = mock_create_agent.call_args
            assert tool in kwargs["tools"]

    @pytest.mark.asyncio
    async def test_llm_task_passes_ui_to_run_agent(self, session):
        # Arrange
        ui = MagicMock()
        task = LLMTask(name="test-task", message="hello")
        task.set_ui(ui)

        # Act & Assert
        with patch("zrb.llm.task.llm_task.create_agent"), patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:

            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

            # Verify the UI set via public set_ui was passed to run_agent
            args, kwargs = mock_run_agent.call_args
            # Now uis is passed as a list
            assert kwargs["ui"] == [ui]

    def test_llm_task_properties(self):
        # Arrange
        task = LLMTask(name="test-task")
        conf = MagicMock()

        # Act
        task.tool_confirmation = conf

        # Assert
        assert task.tool_confirmation == conf
        assert task.prompt_manager is not None

    @pytest.mark.asyncio
    async def test_llm_task_summarization_behavior(self, session):
        # Arrange
        task = LLMTask(
            name="test-task", message="summarize", summarize_command=["summarize"]
        )

        # Act & Assert
        with patch(
            "zrb.llm.task.llm_task.summarize_history", new_callable=AsyncMock
        ) as mock_summarize:
            mock_summarize.return_value = []
            result = await task.async_run(session)

            # Verify behavior: result indicates compression and helper was called
            assert "compressed" in result.lower()
            mock_summarize.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_task_adds_tool_factory_behavior(self, session):
        # Arrange
        tool = MagicMock()
        factory = MagicMock(return_value=tool)
        task = LLMTask(name="test-task", message="hello")
        task.add_tool_factory(factory)

        # Act & Assert
        with patch("zrb.llm.task.llm_task.create_agent"), patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:

            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

            # Factory should have been called with context
            factory.assert_called_once()
