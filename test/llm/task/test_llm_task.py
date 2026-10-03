"""Integration tests for LLMTask: the execution path and its run_agent /
create_agent / summarize_history seams (all patched at this module path).

Pure builder/property unit tests live in ``test_building.py`` and
history/recovery unit tests live in ``test_history.py``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.agent_state import get_current_small_model
from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.std_ui import StdUI
from zrb.session.session import Session


@pytest.fixture
def shared_ctx():
    return SharedContext()


@pytest.fixture
def session(shared_ctx):
    session = Session(shared_ctx=shared_ctx, state_logger=MagicMock())
    return session


class TestLLMTaskExecution:
    """Test LLMTask using only public methods, verifying behavior via orchestrator mocks."""

    @pytest.mark.asyncio
    async def test_llm_task_passes_tools_to_agent(self, session):
        # Arrange
        tool = MagicMock()
        task = LLMTask(name="test-task", message="hello")
        task.append_tool(tool)

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
    async def test_llm_task_resolves_toolset_factories_once(self, session):
        """Toolset factories run once per execution and the SAME instances go
        to the agent.

        Resolving twice (once for the exit stack, once inside agent creation)
        would fire factory side effects — e.g. an MCP server spawn — twice per
        turn and hand the agent instances whose contexts were never entered.
        """
        factory_calls = []

        def toolset_factory(ctx):
            toolset = MagicMock()
            del toolset.__aenter__  # plain toolset: no async context to enter
            factory_calls.append(toolset)
            return toolset

        task = LLMTask(name="test-task", message="hello")
        task.append_toolset_factory(toolset_factory)

        with (
            patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent,
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

            assert len(factory_calls) == 1
            _args, kwargs = mock_create_agent.call_args
            assert kwargs["toolsets"] == factory_calls

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

    @pytest.mark.asyncio
    async def test_llm_task_passes_stream_observers_to_run_agent(self, session):
        first, second, dropped = MagicMock(), MagicMock(), MagicMock()
        task = LLMTask(name="test-task", message="hello")
        task.append_stream_observer(second, dropped)
        task.prepend_stream_observer(first)
        task.remove_stream_observer(dropped)
        task.remove_stream_observer(dropped)  # absent: a no-op

        with (
            patch("zrb.llm.task.llm_task.create_agent"),
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)

            _args, kwargs = mock_run_agent.call_args
            assert kwargs["stream_observers"] == [first, second]

    @pytest.mark.asyncio
    async def test_model_getter_is_called_with_base_model(self, session):
        # Arrange: getter receives the base model and returns a different one
        received = []

        def getter(m):
            received.append(m)
            return "overridden-model"

        task = LLMTask(name="test-task", message="hello", model_getter=getter)

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
        sentinel = MagicMock()

        def renderer(_m):
            return sentinel

        task = LLMTask(
            name="test-task",
            message="hello",
            model="base-model",
            model_renderer=renderer,
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
        ui = MagicMock()
        ui.model = "original-model"

        task = LLMTask(
            name="test-task",
            message="hello",
            model_getter=lambda m: "updated-by-getter",
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
        sentinel = MagicMock()
        task = LLMTask(
            name="test-task",
            message="hello",
            model_getter=lambda m: "getter-result",
            model_renderer=lambda m: sentinel,
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
            name="test-task", message="summarize", summarize_commands=["summarize"]
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
        task.append_tool_factory(factory)

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


@pytest.mark.parametrize("task_class", [LLMTask, LLMChatTask])
def test_stream_observer_surface_matches_and_copies_the_given_list(task_class):
    """Both tasks expose the same stream-observer surface (ADR-0104), and
    neither keeps a reference to the list `set_stream_observers` is handed."""
    task = task_class(name="t")
    first, second = MagicMock(), MagicMock()

    given = [first]
    task.set_stream_observers(given)
    given.append(second)
    assert task.stream_observers == [first]

    task.set_stream_observers([second])

    task.append_stream_observer(first)
    task.prepend_stream_observer(first)
    task.remove_stream_observer(first)
    assert task.stream_observers == [second, first]


@pytest.mark.asyncio
async def test_compress_publishes_the_sessions_small_model(session):
    """`/compress` is handled before the task starts an agent, so it publishes
    the session's model overrides itself; without that the summarizer resolved
    against `CFG` and a `/model small <name>` was silently ignored."""
    ui = StdUI()
    ui.small_model = "openai:session-small"
    task = LLMTask(
        name="compress-task",
        message="/compress",
        summarize_commands=["/compress"],
        ui=ui,
    )
    seen: list = []

    async def fake_summarize(messages, **kwargs):
        seen.append(get_current_small_model())
        return messages

    with patch("zrb.llm.task.llm_task.summarize_history", new=fake_summarize):
        await task.async_run(session)

    assert seen == ["openai:session-small"]


@pytest.mark.asyncio
async def test_compress_publishes_nothing_without_a_session_choice(session):
    """No `/model small` in the session: nothing is bound, so the resolver's own
    chain — and its `CFG` fallback — is left to decide."""
    task = LLMTask(
        name="compress-task",
        message="/compress",
        summarize_commands=["/compress"],
        ui=StdUI(),
    )
    seen: list = []

    async def fake_summarize(messages, **kwargs):
        seen.append(get_current_small_model())
        return messages

    with patch("zrb.llm.task.llm_task.summarize_history", new=fake_summarize):
        await task.async_run(session)

    assert seen == [None]
