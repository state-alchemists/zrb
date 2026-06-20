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
        with (
            patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent,
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):

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
        with (
            patch("zrb.llm.task.llm_task.create_agent"),
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):

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

    @pytest.mark.asyncio
    async def test_model_getter_is_called_with_base_model(self, session):
        # Arrange: getter receives the base model and returns a different one
        from zrb.llm.config.config import LLMConfig

        received = []

        def getter(m):
            received.append(m)
            return "overridden-model"

        config = LLMConfig()
        config.model_getter = getter
        task = LLMTask(name="test-task", message="hello", llm_config=config)

        with (
            patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent,
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
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
        from zrb.llm.config.config import LLMConfig

        sentinel = MagicMock()

        def renderer(_m):
            return sentinel

        config = LLMConfig()
        config.model_renderer = renderer
        task = LLMTask(
            name="test-task",
            message="hello",
            model="base-model",
            llm_config=config,
        )

        with (
            patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent,
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["model"] is sentinel

    @pytest.mark.asyncio
    async def test_model_getter_result_updates_ui_model(self, session):
        # Arrange: getter returns a new model name; UI should reflect it
        from zrb.llm.config.config import LLMConfig

        ui = MagicMock()
        ui.model = "original-model"

        config = LLMConfig()
        config.model_getter = lambda m: "updated-by-getter"
        task = LLMTask(
            name="test-task",
            message="hello",
            llm_config=config,
        )
        task.set_ui(ui)

        with (
            patch("zrb.llm.task.llm_task.create_agent"),
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

        assert ui.model == "updated-by-getter"

    @pytest.mark.asyncio
    async def test_getter_then_renderer_pipeline(self, session):
        # Arrange: getter overrides, renderer wraps — final model passed to create_agent
        from zrb.llm.config.config import LLMConfig

        sentinel = MagicMock()
        config = LLMConfig()
        config.model_getter = lambda m: "getter-result"
        config.model_renderer = lambda m: sentinel
        task = LLMTask(
            name="test-task",
            message="hello",
            llm_config=config,
        )

        with (
            patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent,
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
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
    async def test_llm_task_adds_tool_factory_behavior(self, session):
        # Arrange
        tool = MagicMock()
        factory = MagicMock(return_value=tool)
        task = LLMTask(name="test-task", message="hello")
        task.add_tool_factory(factory)

        # Act & Assert
        with (
            patch("zrb.llm.task.llm_task.create_agent"),
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):

            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

            # Factory should have been called with context
            factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_cancelled_history_with_partial_run(self):
        """PartialRunAccumulator summary is appended when tools were completed."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run._completed_tools.append(
            ("search_files", '{"query": "main.py"}', "Found main.py")
        )

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task._save_cancelled_history(
            history_manager,
            "test-convo",
            [],
            "hello",
            partial_run=partial_run,
        )

        assert history_manager.update.called
        assert history_manager.save.called
        saved = history_manager.update.call_args[0][1]
        assert len(saved) == 3  # user msg + cancelled marker + partial summary
        assert isinstance(saved[-1], ModelRequest)
        assert isinstance(saved[-1].parts[0], UserPromptPart)
        assert "search_files" in saved[-1].parts[0].content
        assert "Found main.py" in saved[-1].parts[0].content

    @pytest.mark.asyncio
    async def test_save_cancelled_history_without_partial_run(self):
        """Backward compat: no partial_run means no summary appended."""

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task._save_cancelled_history(
            history_manager,
            "test-convo",
            [],
            "hello",
        )

        saved = history_manager.update.call_args[0][1]
        assert len(saved) == 2  # user msg + cancelled marker only

    @pytest.mark.asyncio
    async def test_save_cancelled_history_skips_summary_when_no_tools(self):
        """When partial_run has no completed tools, no summary is appended."""
        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.is_interrupted = True

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task._save_cancelled_history(
            history_manager,
            "test-convo",
            [],
            "hello",
            partial_run=partial_run,
        )

        saved = history_manager.update.call_args[0][1]
        assert (
            len(saved) == 2
        )  # user msg + cancelled marker only — no tools to summarize

    @pytest.mark.asyncio
    async def test_handle_run_error_appends_partial_summary(self):
        """PartialRunAccumulator summary is appended when error has zrb_history."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run._completed_tools.append(("search", "{}", "Found foo.py"))

        error = ValueError("API error")
        error.zrb_history = [
            ModelRequest(parts=[UserPromptPart(content="user msg")]),
        ]

        history_manager = MagicMock()
        ctx = MagicMock()
        task = LLMTask(name="test-task")
        task._handle_run_error(
            ctx, history_manager, "test-convo", error, partial_run=partial_run
        )

        saved = history_manager.update.call_args[0][1]
        assert len(saved) == 3  # original + error + partial summary

        # Last message should be the partial summary
        last = saved[-1]
        assert isinstance(last, ModelRequest)
        content = last.parts[0].content
        assert "search" in content
        assert "Found foo.py" in content

    @pytest.mark.asyncio
    async def test_handle_run_error_skips_partial_summary_on_context_length(self):
        """Partial summary is not appended when error is context-length (no history growth)."""
        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run._completed_tools.append(("search", "{}", "Found foo.py"))

        error = ValueError("prompt too long")
        error.zrb_history = []

        history_manager = MagicMock()
        ctx = MagicMock()
        task = LLMTask(name="test-task")
        task._handle_run_error(
            ctx, history_manager, "test-convo", error, partial_run=partial_run
        )

        # Context-length error saves the history as-is without growing it
        saved = history_manager.update.call_args[0][1]
        assert saved == []  # Not grown
