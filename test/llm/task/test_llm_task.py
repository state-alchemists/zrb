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

    def test_custom_model_names_constructor_and_property(self):
        names = ["my-model", "other-model"]
        task = LLMTask(name="test-task", custom_model_names=names)
        assert task.custom_model_names == names

    def test_custom_model_names_setter(self):
        task = LLMTask(name="test-task")
        task.custom_model_names = ["updated-model"]
        assert task.custom_model_names == ["updated-model"]

    def test_model_getter_constructor_and_property(self):
        getter = lambda m: "fixed-model"
        task = LLMTask(name="test-task", model_getter=getter)
        assert task.model_getter is getter

    def test_model_getter_setter(self):
        task = LLMTask(name="test-task")
        getter = lambda m: "fixed-model"
        task.model_getter = getter
        assert task.model_getter is getter

    def test_model_renderer_constructor_and_property(self):
        renderer = lambda m: m
        task = LLMTask(name="test-task", model_renderer=renderer)
        assert task.model_renderer is renderer

    def test_model_renderer_setter(self):
        task = LLMTask(name="test-task")
        renderer = lambda m: m
        task.model_renderer = renderer
        assert task.model_renderer is renderer

    def test_model_getter_none_by_default(self):
        task = LLMTask(name="test-task")
        assert task.model_getter is None

    def test_model_renderer_none_by_default(self):
        task = LLMTask(name="test-task")
        assert task.model_renderer is None

    def test_custom_model_names_none_by_default(self):
        task = LLMTask(name="test-task")
        assert task.custom_model_names is None

    @pytest.mark.asyncio
    async def test_model_getter_is_called_with_base_model(self, session):
        # Arrange: getter receives the base model and returns a different one
        received = []

        def getter(m):
            received.append(m)
            return "overridden-model"

        task = LLMTask(name="test-task", message="hello", model_getter=getter)

        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        # Getter was called once
        assert len(received) == 1
        # create_agent received the getter's return value
        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] == "overridden-model"

    @pytest.mark.asyncio
    async def test_model_renderer_transforms_model_passed_to_agent(self, session):
        # Arrange: renderer wraps model name in a mock Model object
        sentinel = MagicMock()
        renderer = lambda m: sentinel

        task = LLMTask(
            name="test-task",
            message="hello",
            model="base-model",
            model_renderer=renderer,
        )

        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] is sentinel

    @pytest.mark.asyncio
    async def test_model_getter_result_updates_ui_model(self, session):
        # Arrange: getter returns a new model name; UI should reflect it
        ui = MagicMock()
        ui.model = "original-model"

        task = LLMTask(
            name="test-task",
            message="hello",
            model_getter=lambda m: "updated-by-getter",
        )
        task.set_ui(ui)

        with patch("zrb.llm.task.llm_task.create_agent"), patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        assert ui.model == "updated-by-getter"

    @pytest.mark.asyncio
    async def test_getter_then_renderer_pipeline(self, session):
        # Arrange: getter overrides, renderer wraps — final model passed to create_agent
        sentinel = MagicMock()
        task = LLMTask(
            name="test-task",
            message="hello",
            model_getter=lambda m: "getter-result",
            model_renderer=lambda m: sentinel,
        )

        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] is sentinel

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
    async def test_llm_config_getter_used_when_task_getter_is_none(self, session):
        """When task model_getter is None, llm_config.model_getter is applied."""
        from zrb.llm.config.config import LLMConfig

        config = LLMConfig()
        config.model = "base-model"
        config.model_getter = lambda m: "config-getter-result"

        task = LLMTask(name="test-task", message="hello", llm_config=config)
        assert task.model_getter is None  # task-level getter not set

        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] == "config-getter-result"

    @pytest.mark.asyncio
    async def test_llm_config_renderer_used_when_task_renderer_is_none(self, session):
        """When task model_renderer is None, llm_config.model_renderer is applied."""
        from zrb.llm.config.config import LLMConfig

        sentinel = object()
        config = LLMConfig()
        config.model = "base-model"
        config.model_renderer = lambda m: sentinel

        task = LLMTask(name="test-task", message="hello", llm_config=config)
        assert task.model_renderer is None  # task-level renderer not set

        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] is sentinel

    @pytest.mark.asyncio
    async def test_task_getter_takes_precedence_over_llm_config_getter(self, session):
        """Task-level model_getter overrides llm_config.model_getter."""
        from zrb.llm.config.config import LLMConfig

        config = LLMConfig()
        config.model = "base-model"
        config.model_getter = lambda m: "config-getter"

        task = LLMTask(
            name="test-task",
            message="hello",
            llm_config=config,
            model_getter=lambda m: "task-getter",
        )

        with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] == "task-getter"

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
