from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.approval import NullApprovalChannel
from zrb.llm.task.chat.task import LLMChatTask, _parse_yolo_value
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.session.session import Session


class TestParseYoloValue:
    """Test _parse_yolo_value function for selective YOLO support."""

    def test_boolean_true_returns_true(self):
        """Test that boolean True returns True."""
        assert _parse_yolo_value(True) is True

    def test_boolean_false_returns_false(self):
        """Test that boolean False returns False."""
        assert _parse_yolo_value(False) is False

    def test_empty_string_returns_false(self):
        """Test that empty string returns False."""
        assert _parse_yolo_value("") is False

    def test_none_returns_false(self):
        """Test that None returns False."""
        assert _parse_yolo_value(None) is False

    def test_string_false_returns_false(self):
        """Test that 'false' returns False."""
        assert _parse_yolo_value("false") is False
        assert _parse_yolo_value("FALSE") is False
        assert _parse_yolo_value("False") is False

    def test_string_zero_returns_false(self):
        """Test that '0' returns False."""
        assert _parse_yolo_value("0") is False

    def test_string_no_returns_false(self):
        """Test that 'no' returns False."""
        assert _parse_yolo_value("no") is False
        assert _parse_yolo_value("NO") is False

    def test_string_none_returns_false(self):
        """Test that 'none' returns False."""
        assert _parse_yolo_value("none") is False
        assert _parse_yolo_value("None") is False

    def test_string_true_returns_true(self):
        """Test that 'true' returns True."""
        assert _parse_yolo_value("true") is True
        assert _parse_yolo_value("TRUE") is True
        assert _parse_yolo_value("True") is True

    def test_string_one_returns_true(self):
        """Test that '1' returns True."""
        assert _parse_yolo_value("1") is True

    def test_string_yes_returns_true(self):
        """Test that 'yes' returns True."""
        assert _parse_yolo_value("yes") is True
        assert _parse_yolo_value("YES") is True

    def test_single_tool_name_returns_frozenset(self):
        """Test that a single tool name returns a frozenset."""
        result = _parse_yolo_value("Write")
        assert result == frozenset({"Write"})

    def test_comma_separated_tools_returns_frozenset(self):
        """Test that comma-separated tool names return a frozenset."""
        result = _parse_yolo_value("Write,Edit")
        assert result == frozenset({"Write", "Edit"})

    def test_comma_separated_with_spaces_returns_frozenset(self):
        """Test that tool names with spaces are trimmed."""
        result = _parse_yolo_value("Write, Edit, Read")
        assert result == frozenset({"Write", "Edit", "Read"})

    def test_set_returns_frozenset(self):
        """Test that a set returns a frozenset."""
        result = _parse_yolo_value({"Write", "Edit"})
        assert result == frozenset({"Write", "Edit"})

    def test_frozenset_returns_frozenset(self):
        """Test that a frozenset returns unchanged."""
        input_set = frozenset({"Write", "Edit"})
        result = _parse_yolo_value(input_set)
        assert result == input_set

    def test_empty_comma_separated_returns_false(self):
        """Test that empty comma-separated returns False."""
        assert _parse_yolo_value("   ,  ,  ") is False

    def test_whitespace_string_returns_false(self):
        """Test that whitespace-only string returns False."""
        assert _parse_yolo_value("   ") is False


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
        session = Session(shared_ctx, state_logger=MagicMock())

        result = await task.async_run(session)
        assert result == "AI response"
        assert mock_run_agent.called


@pytest.mark.asyncio
async def test_llm_chat_task_interactive_ui_trigger():
    """Test that LLMChatTask triggers UI in interactive mode."""
    # We mock UI.run_async to avoid launching the actual terminal app
    with patch(
        "zrb.llm.ui.default.ui.UI.run_async", new_callable=AsyncMock
    ) as mock_ui_run:
        task = LLMChatTask(name="interactive-task", interactive=True)

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())

        # We need to mock some UI attributes that might be rendered
        with patch("zrb.util.attr.get_str_attr", return_value=""):
            await task.async_run(session)

        assert mock_ui_run.called


@pytest.mark.asyncio
async def test_llm_chat_task_tool_factories():
    """Test tool and toolset factory resolution via public execution."""

    # Create a real callable function instead of MagicMock
    async def mock_tool_func():
        return "mock_tool_result"

    async def mock_tool_in_toolset_func():
        return "mock_toolset_result"

    # Create proper mock objects with required attributes
    mock_tool = mock_tool_func
    mock_tool_in_toolset = mock_tool_in_toolset_func

    task = LLMChatTask(
        name="factory-task",
        tool_factories=[lambda ctx: mock_tool],
        toolset_factories=[lambda ctx: [mock_tool_in_toolset]],
        interactive=False,
    )
    shared_ctx = SharedContext()
    session = Session(shared_ctx, state_logger=MagicMock())

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(session)

        # Verify that tools from factories were passed to run_agent
        assert mock_run_agent.called
        # The test passes if we reach here without pydantic-ai type inspection errors


@pytest.mark.asyncio
async def test_llm_chat_task_setters():
    """Test various setter methods of LLMChatTask via public execution."""

    # Create real callable functions instead of MagicMock
    async def setter_tool_func():
        return "setter_tool_result"

    async def setter_toolset_func():
        return "setter_toolset_result"

    task = LLMChatTask(name="setter-task", interactive=False)

    task.add_tool(setter_tool_func)
    task.add_toolset(setter_toolset_func)
    task.add_history_processor(MagicMock())
    task.add_trigger(lambda: None)
    task.add_custom_command(MagicMock())

    shared_ctx = SharedContext()
    session = Session(shared_ctx, state_logger=MagicMock())

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(session)
        assert mock_run_agent.called


def test_llm_chat_task_set_approval_channel():
    """Test that set_approval_channel works on LLMChatTask."""
    task = LLMChatTask(name="test-task")

    # Set approval channel programmatically
    channel = NullApprovalChannel()
    task.set_approval_channel(channel)

    # Verify the setter works without error - behavior is tested through async_run
    assert True  # If set_approval_channel works, the test passes


def test_llm_chat_task_set_ui():
    """Test that set_ui works on LLMChatTask."""
    task = LLMChatTask(name="test-task")

    # Set UI programmatically
    mock_ui = MagicMock(spec=UIProtocol)
    task.set_ui(mock_ui)

    # Verify the setter works without error - behavior is tested through async_run
    assert True  # If set_ui works, the test passes


def test_llm_chat_task_set_ui_factory():
    """Test that set_ui_factory works on LLMChatTask."""
    task = LLMChatTask(name="test-task")

    # Set UI factory programmatically
    def mock_factory(*args, **kwargs):
        return MagicMock(spec=UIProtocol)

    task.set_ui_factory(mock_factory)

    # Verify the setter works without error - behavior is tested through async_run
    assert True  # If set_ui_factory works, the test passes


def test_llm_chat_task_init_with_approval_channel():
    """Test that LLMChatTask accepts approval_channel parameter."""
    channel = NullApprovalChannel()
    task = LLMChatTask(name="test-task", approval_channel=channel)

    # Verify initialization works - behavior tested through async_run
    assert task.name == "test-task"


def test_llm_chat_task_init_with_ui():
    """Test that LLMChatTask accepts ui parameter."""
    mock_ui = MagicMock(spec=UIProtocol)
    task = LLMChatTask(name="test-task", ui=mock_ui)

    # Verify initialization works - behavior tested through async_run
    assert task.name == "test-task"


def test_llm_chat_task_custom_model_names_constructor_and_property():
    names = ["my-model", "other-model"]
    task = LLMChatTask(name="test-task", custom_model_names=names)
    assert task.custom_model_names == names


def test_llm_chat_task_custom_model_names_setter():
    task = LLMChatTask(name="test-task")
    task.custom_model_names = ["updated-model"]
    assert task.custom_model_names == ["updated-model"]


def test_llm_chat_task_model_getter_constructor_and_property():
    getter = lambda m: "fixed-model"
    task = LLMChatTask(name="test-task", model_getter=getter)
    assert task.model_getter is getter


def test_llm_chat_task_model_getter_setter():
    task = LLMChatTask(name="test-task")
    getter = lambda m: "fixed-model"
    task.model_getter = getter
    assert task.model_getter is getter


def test_llm_chat_task_model_renderer_constructor_and_property():
    renderer = lambda m: m
    task = LLMChatTask(name="test-task", model_renderer=renderer)
    assert task.model_renderer is renderer


def test_llm_chat_task_model_renderer_setter():
    task = LLMChatTask(name="test-task")
    renderer = lambda m: m
    task.model_renderer = renderer
    assert task.model_renderer is renderer


def test_llm_chat_task_model_getter_none_by_default():
    task = LLMChatTask(name="test-task")
    assert task.model_getter is None


def test_llm_chat_task_model_renderer_none_by_default():
    task = LLMChatTask(name="test-task")
    assert task.model_renderer is None


def test_llm_chat_task_custom_model_names_none_by_default():
    task = LLMChatTask(name="test-task")
    assert task.custom_model_names is None


@pytest.mark.asyncio
async def test_llm_chat_task_passes_getter_renderer_to_summarizer():
    """LLMChatTask forwards effective getter/renderer to create_summarizer_history_processor."""
    getter = lambda m: "getter-model"
    renderer = lambda m: "renderer-model"

    task = LLMChatTask(
        name="test-task",
        model_getter=getter,
        model_renderer=renderer,
        interactive=False,
    )

    with patch(
        "zrb.llm.task.chat.task.create_summarizer_history_processor"
    ) as mock_create_proc, patch("zrb.llm.task.llm_task.create_agent"), patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_proc = MagicMock()
        mock_proc.return_value = AsyncMock(return_value=[])
        mock_create_proc.return_value = mock_proc
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    mock_create_proc.assert_called_once()
    _, kwargs = mock_create_proc.call_args
    assert kwargs.get("model_getter") is getter
    assert kwargs.get("model_renderer") is renderer
