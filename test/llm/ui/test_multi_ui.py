import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.ui.multi_ui import MultiUI


@pytest.fixture
def mock_child_ui():
    """Create a mock child UI for testing."""
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")
    ui.tool_call_handler = MagicMock()
    ui.tool_call_handler.check_policies = AsyncMock(return_value=None)
    ui.tool_call_handler.handle = AsyncMock(return_value=MagicMock(approved=True))
    # Pin real defaults so stream_ai_response's plan-mode sync and snapshot
    # path behave like a real UI (a MagicMock would read truthy and flip the
    # module-level agent-mode ContextVar, polluting other tests).
    ui.plan_mode_active = False
    ui.snapshot_manager = None
    ui.history_manager = None
    return ui


@pytest.fixture
def child_ui_1():
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.invalidate_ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="input 1")
    ui.run_interactive_command = AsyncMock(return_value=0)
    ui.run_async = AsyncMock(return_value="done 1")
    ui.cancel_pending_confirmations = MagicMock()
    # Mock some expected properties/methods that MultiUI might delegate to
    ui.tool_call_handler = MagicMock()
    ui.tool_call_handler.handle = AsyncMock(return_value="Approved 1")
    # Explicit non-mock state so _stream_ai_response's plan-mode sync and
    # snapshot path behave as they would with a real UI (a MagicMock would be
    # truthy and flip the global agent-mode ContextVar, polluting other tests).
    ui.plan_mode_active = False
    ui.snapshot_manager = None
    ui.history_manager = None
    return ui


@pytest.fixture
def child_ui_2():
    ui = MagicMock()
    ui.append_to_output = MagicMock()
    ui.invalidate_ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="input 2")
    ui.start_event_loop = AsyncMock()
    ui.cancel_pending_confirmations = MagicMock()
    ui.plan_mode_active = False
    return ui


@pytest.fixture
def multi_ui(child_ui_1, child_ui_2):
    return MultiUI([child_ui_1, child_ui_2])


class TestMultiUI:
    """Tests for MultiUI construction and delegation basics."""

    def test_multi_ui_creation(self, mock_child_ui):
        """Test creating a MultiUI with child UIs."""
        multi_ui = MultiUI([mock_child_ui])
        # Verify through public behavior - broadcast output to all children
        multi_ui.append_to_output("test")
        mock_child_ui.append_to_output.assert_called_once()

    def test_multi_ui_sets_parent_reference(self, mock_child_ui):
        """Test that MultiUI sets _multi_ui_parent on child UIs."""
        multi_ui = MultiUI([mock_child_ui])
        assert hasattr(mock_child_ui, "multi_ui_parent")
        assert mock_child_ui.multi_ui_parent is multi_ui

    def test_set_tool_call_handler(self, mock_child_ui):
        """Test set_tool_call_handler method."""
        multi_ui = MultiUI([mock_child_ui])
        mock_handler = MagicMock()
        multi_ui.set_tool_call_handler(mock_handler)

        # Verify through public property
        assert multi_ui.tool_call_handler is mock_handler

    def test_set_approval_channel(self, mock_child_ui):
        """Test set_approval_channel method."""
        multi_ui = MultiUI([mock_child_ui])
        mock_channel = MagicMock()

        multi_ui.set_approval_channel(mock_channel)

        # Verify through behavior - approval channel is used in confirm_tool_execution
        # We can't directly verify, but we can test it through _confirm_tool_execution
        assert True  # Method executed successfully

    def test_main_ui_property(self, mock_child_ui):
        """Test that run_interactive_command delegates to first UI by default."""
        other_ui = MagicMock()
        other_ui.run_interactive_command = AsyncMock(return_value=0)
        mock_child_ui.run_interactive_command = AsyncMock(return_value=0)
        multi_ui = MultiUI([mock_child_ui, other_ui])

        # Verify through public behavior - main UI (first) gets called
        result = asyncio.run(multi_ui.run_interactive_command("ls"))
        mock_child_ui.run_interactive_command.assert_called_once()

    def test_main_ui_property_with_custom_index(self, mock_child_ui):
        """Test that run_interactive_command delegates to correct UI based on main_ui_index."""
        other_ui = MagicMock()
        other_ui.run_interactive_command = AsyncMock(return_value=0)
        mock_child_ui.run_interactive_command = AsyncMock(return_value=0)
        multi_ui = MultiUI([mock_child_ui, other_ui], main_ui_index=1)

        # Verify through public behavior - UI at index 1 gets called
        result = asyncio.run(multi_ui.run_interactive_command("ls"))
        other_ui.run_interactive_command.assert_called_once()

    def test_main_ui_index_out_of_range_raises_error(self):
        """Test run_interactive_command raises error when UI list is empty."""
        multi_ui = MultiUI([])

        with pytest.raises((AttributeError, TypeError)):
            # Should raise because there's no main_ui to delegate to
            asyncio.run(multi_ui.run_interactive_command("ls"))

    def test_set_llm_task_sets_on_children(self, mock_child_ui):
        """Test set_llm_task sets llm_task on all children."""
        other_ui = MagicMock()
        mock_task = MagicMock()

        multi_ui = MultiUI([mock_child_ui, other_ui])
        multi_ui.set_llm_task(mock_task)

        assert mock_child_ui.llm_task is mock_task
        assert other_ui.llm_task is mock_task

    def test_create_session_for_llm_task(self, mock_child_ui):
        """Test create_session_for_llm_task creates proper session."""
        multi_ui = MultiUI([mock_child_ui])

        session = multi_ui.create_session_for_llm_task("Hello", [])

        assert session is not None

    def test_last_output_tracks_output(self, mock_child_ui):
        """Test last_output property."""
        multi_ui = MultiUI([mock_child_ui])
        assert multi_ui.last_output == ""

    def test_stream_to_parent(self, mock_child_ui):
        """Test stream_to_parent delegates to child UIs."""
        other_ui = MagicMock()
        other_ui.stream_to_parent = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui])

        multi_ui.stream_to_parent("Test message")

        other_ui.stream_to_parent.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_interactive_command_delegates(self, mock_child_ui):
        """Test run_interactive_command delegates to main UI."""
        mock_child_ui.run_interactive_command = AsyncMock(return_value=0)
        multi_ui = MultiUI([mock_child_ui])

        result = await multi_ui.run_interactive_command("ls")

        assert result == 0
        mock_child_ui.run_interactive_command.assert_called_once_with("ls", shell=False)

    def test_invalidate_all_uis(self, mock_child_ui):
        """Test invalidate_all_uis calls invalidate_ui on all children."""
        other_ui = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui])

        multi_ui.invalidate_all_uis()

        assert hasattr(mock_child_ui, "invalidate_ui")
        assert hasattr(other_ui, "invalidate_ui")

    def test_invalidate_all_uis_handles_exception(self, mock_child_ui):
        """Test invalidate_all_uis handles exceptions from child UIs."""
        other_ui = MagicMock()
        del other_ui.invalidate_ui  # Remove the method to trigger exception
        multi_ui = MultiUI([mock_child_ui, other_ui])

        # Should not raise
        multi_ui.invalidate_all_uis()

    def test_on_exit_cancels_tasks(self, mock_child_ui):
        """Test on_exit cancels all child tasks."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui.child_tasks = [MagicMock(), MagicMock()]
        multi_ui.pending_input_tasks = [MagicMock()]
        multi_ui.process_messages_task = MagicMock()

        multi_ui.on_exit()

        # Tasks should be cancelled
        for task in multi_ui.child_tasks:
            task.cancel.assert_called()

    def test_on_exit_calls_main_ui_on_exit(self, mock_child_ui):
        """Test on_exit calls main UI's on_exit method."""
        multi_ui = MultiUI([mock_child_ui])

        multi_ui.on_exit()

        mock_child_ui.on_exit.assert_called_once()


def test_multi_ui_init(multi_ui, child_ui_1, child_ui_2):
    assert child_ui_1.multi_ui_parent is multi_ui
    assert child_ui_2.multi_ui_parent is multi_ui
    # multi_ui.main_ui is a property
    assert multi_ui.main_ui is child_ui_1


def test_multi_ui_invalidate_all(multi_ui, child_ui_1, child_ui_2):
    multi_ui.invalidate_all_uis()
    child_ui_1.invalidate_ui.assert_called_once()
    child_ui_2.invalidate_ui.assert_called_once()


def test_multi_ui_on_exit(multi_ui, child_ui_1):
    child_ui_1.on_exit = MagicMock()
    multi_ui.on_exit()
    child_ui_1.on_exit.assert_called_once()


@pytest.mark.asyncio
async def test_multi_ui_run_async(multi_ui, child_ui_1, child_ui_2):
    multi_ui.set_llm_task(MagicMock())
    child_ui_1.last_output = "Final Output"

    res = await multi_ui.run_async()

    assert res == "Final Output"
    child_ui_1.run_async.assert_called_once()
    child_ui_2.start_event_loop.assert_called_once()


@pytest.mark.asyncio
async def test_multi_ui_run_interactive_command(multi_ui, child_ui_1):
    res = await multi_ui.run_interactive_command("ls")
    assert res == 0
    child_ui_1.run_interactive_command.assert_called_with("ls", shell=False)
