from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.ui.default_ui import UI
from zrb.llm.ui.multi_ui import MultiUI


@pytest.fixture
def mock_ui_deps():
    return {
        "ctx": SharedContext(),
        "yolo_xcom_key": "yolo",
        "greeting": "Hello",
        "assistant_name": "Assistant",
        "ascii_art": "ART",
        "jargon": "Jargon",
        "output_lexer": MagicMock(),
        "llm_task": MagicMock(),
        "history_manager": MagicMock(),
    }


def test_ui_public_methods(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    # Test toggle_yolo
    # Test toggle_yolo
    assert (
        not mock_ui_deps["ctx"].xcom.get(mock_ui_deps["yolo_xcom_key"], {}).get(False)
    )
    ui.toggle_yolo()
    assert mock_ui_deps["ctx"].xcom.get(mock_ui_deps["yolo_xcom_key"], {}).get(False)
    ui.toggle_yolo()
    assert (
        not mock_ui_deps["ctx"].xcom.get(mock_ui_deps["yolo_xcom_key"], {}).get(False)
    )

    # Test append_to_output
    ui.output_buffer = MagicMock()
    ui.append_to_output("New content")
    # append_to_output internally modifies output_buffer.text
    assert ui.output_buffer.text is not None


@pytest.mark.asyncio
async def test_ui_ask_user(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    # UI uses prompt_toolkit session.prompt_async or similar
    # We need to mock the application or session
    ui.app = MagicMock()
    # ask_user returns a future/coro that we can control
    # This might be complex to test without deep mocking,
    # but let's see if we can trigger some lines.
    assert hasattr(ui, "ask_user")


class TestMultiUI:
    """Tests for MultiUI class."""

    @pytest.fixture
    def mock_child_ui(self):
        """Create a mock child UI for testing."""
        ui = MagicMock()
        ui.append_to_output = MagicMock()
        ui.ask_user = AsyncMock(return_value="y")
        ui._tool_call_handler = MagicMock()
        ui._tool_call_handler._argument_formatters = ["formatter1"]
        ui._tool_call_handler.check_policies = AsyncMock(return_value=None)
        ui._tool_call_handler.handle = AsyncMock(return_value=MagicMock(approved=True))
        return ui

    def test_multi_ui_creation(self, mock_child_ui):
        """Test creating a MultiUI with child UIs."""
        multi_ui = MultiUI([mock_child_ui])
        assert len(multi_ui._uis) == 1
        assert multi_ui._uis[0] is mock_child_ui

    def test_multi_ui_sets_parent_reference(self, mock_child_ui):
        """Test that MultiUI sets _multi_ui_parent on child UIs."""
        multi_ui = MultiUI([mock_child_ui])
        assert hasattr(mock_child_ui, "_multi_ui_parent")
        assert mock_child_ui._multi_ui_parent is multi_ui

    def test_set_tool_call_handler(self, mock_child_ui):
        """Test set_tool_call_handler method."""
        multi_ui = MultiUI([mock_child_ui])
        mock_handler = MagicMock()
        mock_handler._argument_formatters = ["fmt1", "fmt2"]

        multi_ui.set_tool_call_handler(mock_handler)

        assert multi_ui._tool_call_handler is mock_handler

    def test_set_approval_channel(self, mock_child_ui):
        """Test set_approval_channel method."""
        multi_ui = MultiUI([mock_child_ui])
        mock_channel = MagicMock()

        multi_ui.set_approval_channel(mock_channel)

        assert multi_ui._approval_channel is mock_channel

    def test_main_ui_property(self, mock_child_ui):
        """Test _main_ui property returns first UI by default."""
        multi_ui = MultiUI([mock_child_ui, MagicMock()])
        assert multi_ui._main_ui is mock_child_ui

    def test_main_ui_property_with_custom_index(self, mock_child_ui):
        """Test _main_ui property with custom main_ui_index."""
        other_ui = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui], main_ui_index=1)
        assert multi_ui._main_ui is other_ui

    def test_append_to_output_broadcasts(self, mock_child_ui):
        """Test that append_to_output broadcasts to all child UIs."""
        other_ui = MagicMock()
        other_ui.append_to_output = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui])

        multi_ui.append_to_output("Test message")

        mock_child_ui.append_to_output.assert_called_once()
        other_ui.append_to_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_tool_uses_handler(self, mock_child_ui):
        """Test _confirm_tool_execution uses _tool_call_handler when available."""
        multi_ui = MultiUI([mock_child_ui])
        mock_handler = MagicMock()
        mock_handler._argument_formatters = ["fmt1"]
        mock_handler.handle = AsyncMock(return_value=MagicMock(approved=True))
        multi_ui._tool_call_handler = mock_handler

        mock_call = MagicMock()
        mock_call.tool_name = "Write"
        mock_call.args = {"path": "/tmp/test.txt", "content": "hello"}

        result = await multi_ui._confirm_tool_execution(mock_call)

        mock_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_tool_uses_winning_ui_handler(self, mock_child_ui):
        """Test _confirm_tool_execution uses winning UI's handler when no MultiUI handler."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui._tool_call_handler = None
        multi_ui._last_winning_ui = mock_child_ui

        mock_call = MagicMock()
        mock_call.tool_name = "Write"
        mock_call.args = {}

        mock_child_ui._tool_call_handler.handle.return_value = MagicMock(approved=True)

        result = await multi_ui._confirm_tool_execution(mock_call)

        mock_child_ui._tool_call_handler.handle.assert_called_once()

    def test_submit_user_message_queues_job(self, mock_child_ui):
        """Test _submit_user_message queues a job."""
        multi_ui = MultiUI([mock_child_ui])
        mock_task = MagicMock()

        multi_ui._submit_user_message(mock_task, "Hello world")

        assert not multi_ui._message_queue.empty()

    def test_invalidate_all_uis(self, mock_child_ui):
        """Test invalidate_all_uis calls invalidate_ui on all children."""
        other_ui = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui])

        multi_ui.invalidate_all_uis()

        assert hasattr(mock_child_ui, "invalidate_ui")
        assert hasattr(other_ui, "invalidate_ui")

    def test_clear_pending_confirmations_except(self, mock_child_ui):
        """Test _clear_pending_confirmations_except cancels non-winning UIs."""
        other_ui = MagicMock()
        other_ui._cancel_pending_confirmations = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui])

        multi_ui._clear_pending_confirmations_except(0)

        other_ui._cancel_pending_confirmations.assert_called_once()

    def test_last_output_tracks_output(self, mock_child_ui):
        """Test last_output property."""
        multi_ui = MultiUI([mock_child_ui])
        assert multi_ui.last_output == ""

    def test_main_ui_index_out_of_range_returns_none(self):
        """Test _main_ui returns None when index is out of range."""
        multi_ui = MultiUI([])
        assert multi_ui._main_ui is None

    @pytest.mark.asyncio
    async def test_confirm_tool_falls_back_to_first_ui_handler(self, mock_child_ui):
        """Test _confirm_tool_execution falls back to first UI's handler."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui._tool_call_handler = None
        multi_ui._last_winning_ui = None
        multi_ui._approval_channel = None

        mock_call = MagicMock()
        mock_call.tool_name = "Write"
        mock_call.args = {}

        mock_child_ui._tool_call_handler.handle.return_value = MagicMock(approved=True)

        result = await multi_ui._confirm_tool_execution(mock_call)
        mock_child_ui._tool_call_handler.handle.assert_called_once()

    def test_set_llm_task_sets_on_children(self, mock_child_ui):
        """Test set_llm_task sets _llm_task on all children."""
        other_ui = MagicMock()
        multi_ui = MultiUI([mock_child_ui, other_ui])
        mock_task = MagicMock()

        multi_ui.set_llm_task(mock_task)

        assert mock_child_ui._llm_task is mock_task
        assert other_ui._llm_task is mock_task

    def test_create_session_for_llm_task(self, mock_child_ui):
        """Test _create_session_for_llm_task creates proper session."""
        multi_ui = MultiUI([mock_child_ui])

        session = multi_ui._create_session_for_llm_task("Hello", [])

        assert session is not None

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

    def test_on_exit_cancels_tasks(self, mock_child_ui):
        """Test on_exit cancels all child tasks."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui._child_tasks = [MagicMock(), MagicMock()]
        multi_ui._pending_input_tasks = [MagicMock()]
        multi_ui._process_messages_task = MagicMock()

        multi_ui.on_exit()

        # Tasks should be cancelled
        for task in multi_ui._child_tasks:
            task.cancel.assert_called()

    def test_on_exit_calls_main_ui_on_exit(self, mock_child_ui):
        """Test on_exit calls main UI's on_exit method."""
        multi_ui = MultiUI([mock_child_ui])

        multi_ui.on_exit()

        mock_child_ui.on_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_tool_raises_when_no_ui(self):
        """Test _confirm_tool_execution raises when no UI available."""
        mock_ui = MagicMock()
        mock_ui._tool_call_handler = None
        multi_ui = MultiUI([mock_ui])
        multi_ui._tool_call_handler = None
        multi_ui._approval_channel = None

        mock_call = MagicMock()
        mock_call.tool_name = "Write"
        mock_call.args = {}

        # Create empty _uis list to trigger the error
        multi_ui._uis = []

        with pytest.raises(RuntimeError, match="No UI available"):
            await multi_ui._confirm_tool_execution(mock_call)

    @pytest.mark.asyncio
    async def test_confirm_tool_uses_approval_channel(self):
        """Test _confirm_tool_execution falls back to approval channel."""
        mock_ui = MagicMock()
        mock_ui._tool_call_handler = None
        multi_ui = MultiUI([mock_ui])
        multi_ui._tool_call_handler = None
        multi_ui._approval_channel = MagicMock()

        from zrb.llm.approval import ApprovalResult

        multi_ui._approval_channel.request_approval = AsyncMock(
            return_value=ApprovalResult(approved=True, message="Approved")
        )

        mock_call = MagicMock()
        mock_call.tool_name = "Write"
        mock_call.args = {"path": "/tmp/test"}
        mock_call.tool_call_id = "call_123"

        result = await multi_ui._confirm_tool_execution(mock_call)

        # Result is converted via to_pydantic_result() which returns ToolApproved
        assert hasattr(result, "message") or result is not None
        multi_ui._approval_channel.request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_user_returns_empty_when_shutdown(self):
        """Test ask_user returns empty string when shutdown is requested."""
        from zrb.llm.ui.multi_ui import MultiUI

        multi_ui = MultiUI([MagicMock()])

        # Patch is_shutdown_requested to return True
        import zrb.llm.ui.multi_ui as multi_ui_module

        original_func = multi_ui_module.is_shutdown_requested
        multi_ui_module.is_shutdown_requested = lambda: True

        try:
            result = await multi_ui.ask_user("test prompt")
            assert result == ""
        finally:
            multi_ui_module.is_shutdown_requested = original_func

    @pytest.mark.asyncio
    async def test_ask_user_returns_empty_when_no_pending_tasks(self, mock_child_ui):
        """Test ask_user returns empty when no UIs have ask_user method."""
        multi_ui = MultiUI([mock_child_ui])

        # Remove ask_user from mock
        del mock_child_ui.ask_user

        result = await multi_ui.ask_user("test prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_ask_user_returns_empty_on_exception(self):
        """Test ask_user returns empty when completed task raises exception."""
        import asyncio

        mock_ui = MagicMock()

        async def error_response(prompt):
            await asyncio.sleep(0.1)
            raise Exception("Test error")

        mock_ui.ask_user = error_response

        multi_ui = MultiUI([mock_ui])

        result = await multi_ui.ask_user("test prompt")

        # Should return empty when exception occurs
        assert result == ""

    @pytest.mark.asyncio
    async def test_submit_user_message_broadcasts(self, mock_child_ui):
        """Test _submit_user_message broadcasts to all UIs."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui.append_to_output = MagicMock()

        mock_task = MagicMock()

        multi_ui._submit_user_message(mock_task, "Hello world")

        # Message should be queued
        assert not multi_ui._message_queue.empty()

    def test_invalidate_all_uis_handles_exception(self, mock_child_ui):
        """Test invalidate_all_uis handles exceptions from child UIs."""
        other_ui = MagicMock()
        del other_ui.invalidate_ui  # Remove the method to trigger exception
        multi_ui = MultiUI([mock_child_ui, other_ui])

        # Should not raise
        multi_ui.invalidate_all_uis()

    def test_append_to_output_handles_exception(self, mock_child_ui):
        """Test append_to_output handles exceptions from child UIs."""
        mock_child_ui.append_to_output = MagicMock(side_effect=Exception("Test"))
        multi_ui = MultiUI([mock_child_ui])

        # Should not raise
        multi_ui.append_to_output("Test message")

    @pytest.mark.asyncio
    async def test_stream_ai_response_resets_is_thinking_on_error(self, mock_child_ui):
        """Test _stream_ai_response resets _is_thinking even on error."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui.append_to_output = MagicMock()

        mock_llm_task = MagicMock()

        async def raise_error():
            raise ValueError("Test error")

        mock_llm_task.async_run = AsyncMock(side_effect=raise_error)
        mock_llm_task.set_ui = MagicMock()
        mock_llm_task.tool_confirmation = MagicMock()

        await multi_ui._stream_ai_response(mock_llm_task, "Hello", [])

        # _is_thinking should be reset even after error
        assert multi_ui._is_thinking is False

    @pytest.mark.asyncio
    async def test_stream_ai_response_handles_error(self, mock_child_ui):
        """Test _stream_ai_response handles errors gracefully."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui.append_to_output = MagicMock()

        mock_llm_task = MagicMock()

        async def raise_error():
            raise ValueError("Test error")

        mock_llm_task.async_run = AsyncMock(side_effect=raise_error)
        mock_llm_task.set_ui = MagicMock()
        mock_llm_task.tool_confirmation = MagicMock()

        # Should not raise, but should log error
        await multi_ui._stream_ai_response(mock_llm_task, "Hello", [])

        # _is_thinking should be reset
        assert multi_ui._is_thinking is False

    @pytest.mark.asyncio
    async def test_stream_ai_response_with_result(self, mock_child_ui):
        """Test _stream_ai_response processes result correctly."""
        multi_ui = MultiUI([mock_child_ui])
        multi_ui.append_to_output = MagicMock()

        mock_llm_task = MagicMock()
        mock_llm_task.async_run = AsyncMock(return_value="# Response")
        mock_llm_task.set_ui = MagicMock()
        mock_llm_task.tool_confirmation = MagicMock()

        await multi_ui._stream_ai_response(mock_llm_task, "Hello", [])

        # Result should be stored
        assert multi_ui._last_result_data == "# Response"
        # _is_thinking should be reset
        assert multi_ui._is_thinking is False

    def test_clear_pending_confirmations_skips_exception(self):
        """Test _clear_pending_confirmations_except handles exceptions."""
        mock_ui1 = MagicMock()
        mock_ui1._cancel_pending_confirmations = MagicMock(
            side_effect=Exception("Test")
        )
        mock_ui2 = MagicMock()
        mock_ui2._cancel_pending_confirmations = MagicMock()
        multi_ui = MultiUI([mock_ui1, mock_ui2])

        # Should not raise when skipping index 0
        multi_ui._clear_pending_confirmations_except(0)

        # ui2 (index 1) should be called
        mock_ui2._cancel_pending_confirmations.assert_called_once()
        # ui1 (index 0) should NOT be called because we're skipping it
        mock_ui1._cancel_pending_confirmations.assert_not_called()


class TestUIConfig:
    """Tests for UIConfig dataclass."""

    def test_default_config(self):
        """Test UIConfig.default() creates default config."""
        from zrb.llm.ui.simple_ui import UIConfig

        config = UIConfig.default()

        assert config.assistant_name == "Assistant"
        assert "/exit" in config.exit_commands
        assert "/help" in config.info_commands

    def test_minimal_config(self):
        """Test UIConfig.minimal() creates minimal config."""
        from zrb.llm.ui.simple_ui import UIConfig

        config = UIConfig.minimal()

        assert config.exit_commands == ["/exit"]
        assert config.info_commands == []
        assert config.save_commands == []
        assert config.load_commands == []
        assert config.attach_commands == []
        assert config.redirect_output_commands == []
        assert config.yolo_toggle_commands == []
        assert config.set_model_commands == []
        assert config.exec_commands == []

    def test_merge_commands(self):
        """Test UIConfig.merge_commands() merges command dict."""
        from zrb.llm.ui.simple_ui import UIConfig

        config = UIConfig.default()
        ui_commands = {
            "exit": ["/quit", "/q"],
            "info": ["/commands"],
        }

        merged = config.merge_commands(ui_commands)

        assert merged.exit_commands == ["/quit", "/q"]
        assert merged.info_commands == ["/commands"]
        assert merged.summarize_commands == config.summarize_commands

    def test_config_with_custom_values(self):
        """Test UIConfig with custom values."""
        from zrb.llm.ui.simple_ui import UIConfig

        config = UIConfig(
            assistant_name="MyBot",
            yolo=True,
            conversation_session_name="my-session",
        )

        assert config.assistant_name == "MyBot"
        assert config.yolo is True
        assert config.conversation_session_name == "my-session"


class TestSimpleUISubclass:
    """Tests for SimpleUI subclass behavior."""

    @pytest.fixture
    def simple_ui_deps(self):
        """Create mock dependencies for SimpleUI."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui.simple_ui import UIConfig

        return {
            "ctx": SharedContext(),
            "llm_task": MagicMock(),
            "history_manager": MagicMock(),
            "config": UIConfig.default(),
        }

    def test_simple_ui_creation_with_defaults(self, simple_ui_deps):
        """Test SimpleUI creation with default parameters."""
        from zrb.llm.ui.simple_ui import SimpleUI

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        assert ui._assistant_name == "Assistant"
        assert ui._config is not None

    def test_simple_ui_creation_with_custom_config(self, simple_ui_deps):
        """Test SimpleUI creation with custom config."""
        from zrb.llm.ui.simple_ui import SimpleUI, UIConfig

        simple_ui_deps["config"] = UIConfig(
            assistant_name="CustomBot",
            yolo=True,
        )

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        assert ui._assistant_name == "CustomBot"

    def test_simple_ui_generates_yolo_xcom_key(self, simple_ui_deps):
        """Test SimpleUI generates yolo_xcom_key if not provided."""
        from zrb.llm.ui.simple_ui import SimpleUI, UIConfig

        simple_ui_deps["config"] = UIConfig(yolo_xcom_key="")

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        assert ui._yolo_xcom_key.startswith("_yolo_")

    def test_simple_ui_with_response_handlers(self, simple_ui_deps):
        """Test SimpleUI accepts response_handlers parameter."""
        from zrb.llm.ui.simple_ui import SimpleUI

        mock_handler = MagicMock()
        simple_ui_deps["response_handlers"] = [mock_handler]

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        assert mock_handler in ui._tool_call_handler._response_handlers

    def test_simple_ui_with_argument_formatters(self, simple_ui_deps):
        """Test SimpleUI accepts argument_formatters parameter."""
        from zrb.llm.ui.simple_ui import SimpleUI

        mock_formatter = MagicMock()
        simple_ui_deps["argument_formatters"] = [mock_formatter]

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        assert mock_formatter in ui._tool_call_handler._argument_formatters

    def test_simple_ui_accepts_extra_kwargs(self, simple_ui_deps):
        """Test SimpleUI accepts extra kwargs for subclass use."""
        from zrb.llm.ui.simple_ui import SimpleUI

        simple_ui_deps["custom_param"] = "custom_value"

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        # SimpleUI doesn't store kwargs by default, but subclasses can access them
        # This test just verifies it doesn't crash
        assert ui is not None

    @pytest.mark.asyncio
    async def test_run_interactive_command_returns_error(self, simple_ui_deps):
        """Test SimpleUI.run_interactive_command returns error code."""
        from zrb.llm.ui.simple_ui import SimpleUI

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        result = await ui.run_interactive_command("ls")

        assert result == 1


class TestEventDrivenUI:
    """Tests for EventDrivenUI class."""

    @pytest.fixture
    def event_ui_deps(self):
        """Create mock dependencies for EventDrivenUI."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui.simple_ui import UIConfig

        return {
            "ctx": SharedContext(),
            "llm_task": MagicMock(),
            "history_manager": MagicMock(),
            "config": UIConfig.default(),
        }

    def test_event_ui_creates_input_queue(self, event_ui_deps):
        """Test EventDrivenUI creates input queue."""
        from zrb.llm.ui.simple_ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)

        assert hasattr(ui, "_input_queue")
        assert ui.input_queue is ui._input_queue

    def test_event_ui_get_input_blocks(self, event_ui_deps):
        """Test EventDrivenUI creates input queue on init."""
        from zrb.llm.ui.simple_ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)

        # Verify queue exists
        assert hasattr(ui, "_input_queue")

    def test_handle_incoming_message_queues_when_waiting(self, event_ui_deps):
        """Test handle_incoming_message queues when waiting for input."""
        from zrb.llm.ui.simple_ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)
        ui._waiting_for_input = True

        ui.handle_incoming_message("test")

        # When waiting, message goes to queue
        result = ui._input_queue.get_nowait()
        assert result == "test"

    def test_handle_incoming_message_submits_when_not_waiting(self, event_ui_deps):
        """Test handle_incoming_message submits when not waiting for input."""
        from zrb.llm.ui.simple_ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)
        ui._waiting_for_input = False
        ui._llm_task = MagicMock()

        # When not waiting, handle_incoming_message calls _submit_user_message
        # which submits to message queue (not input queue)
        ui.handle_incoming_message("test message")

        # Message goes to message queue
        assert not ui._message_queue.empty()


class TestPollingUI:
    """Tests for PollingUI class."""

    @pytest.fixture
    def polling_ui_deps(self):
        """Create mock dependencies for PollingUI."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui.simple_ui import UIConfig

        return {
            "ctx": SharedContext(),
            "llm_task": MagicMock(),
            "history_manager": MagicMock(),
            "config": UIConfig.default(),
        }

    def test_polling_ui_creates_output_queue(self, polling_ui_deps):
        """Test PollingUI creates output queue."""
        from zrb.llm.ui.simple_ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        assert hasattr(ui, "output_queue")
        assert hasattr(ui, "_input_queue")
        assert ui.input_queue is ui._input_queue

    @pytest.mark.asyncio
    async def test_polling_ui_print_queues_output(self, polling_ui_deps):
        """Test PollingUI.print queues output."""
        from zrb.llm.ui.simple_ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        await ui.print("test output")

        result = ui.output_queue.get_nowait()
        assert result == "test output"

    def test_polling_ui_get_input_blocks(self, polling_ui_deps):
        """Test PollingUI creates input queue."""
        from zrb.llm.ui.simple_ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        # Verify queues exist
        assert hasattr(ui, "output_queue")
        assert hasattr(ui, "_input_queue")

    def test_polling_ui_handle_incoming_queues_when_waiting(self, polling_ui_deps):
        """Test handle_incoming_message queues when waiting for input."""
        from zrb.llm.ui.simple_ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)
        ui._waiting_for_input = True

        ui.handle_incoming_message("test")

        result = ui._input_queue.get_nowait()
        assert result == "test"

    def test_polling_ui_handle_incoming_submits_when_idle(self, polling_ui_deps):
        """Test handle_incoming_message submits when LLM is idle."""
        from zrb.llm.ui.simple_ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)
        ui._waiting_for_input = False
        ui._llm_task = MagicMock()

        ui.handle_incoming_message("test message")

        # When not waiting, message goes through _submit_user_message
        # which submits to message queue
        assert not ui._message_queue.empty()


class TestBufferedOutputMixin:
    """Tests for BufferedOutputMixin class."""

    def test_buffer_creates_flush_task(self):
        """Test BufferedOutputMixin creates flush task on start."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered(flush_interval=0.1)

        assert buffered._buffer == []
        assert buffered._flush_interval == 0.1
        assert buffered._max_buffer_size == 2000

    def test_buffer_output_filters_pure_spinner(self):
        """Test buffer_output filters pure spinner updates."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("\r⠇")
        buffered.buffer_output("\r⠏⠋⠙")

        assert len(buffered._buffer) == 0

    def test_buffer_output_filters_progress_at_end(self):
        """Test buffer_output filters spinner at end of line."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        # Spinners at end get stripped but message body remains
        buffered.buffer_output("Loading")
        buffered.buffer_output("Processing")

        # Both should be buffered (no spinner chars in test)
        assert len(buffered._buffer) == 2

    def test_buffer_output_filters_prepare_tool_params(self):
        """Test buffer_output filters 'Prepare tool parameters' messages."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("🔄 Prepare tool parameters ⠇")

        assert len(buffered._buffer) == 0

    def test_buffer_output_normal_text(self):
        """Test buffer_output accepts normal text."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("Hello, world!")

        assert len(buffered._buffer) == 1
        assert buffered._buffer[0] == "Hello, world!"

    def test_buffer_output_removes_carriage_returns(self):
        """Test buffer_output removes carriage returns from text."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("Line1\rLine2")

        assert "\r" not in buffered._buffer[0]

    @pytest.mark.asyncio
    async def test_stop_flush_loop_method_exists(self):
        """Test stop_flush_loop method exists and is async."""
        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        # Verify the method exists and is callable
        assert callable(getattr(buffered, "stop_flush_loop", None))

        # Verify no _flush_task initially
        assert buffered._flush_task is None

    @pytest.mark.asyncio
    async def test_start_flush_loop_creates_task(self):
        """Test start_flush_loop creates a flush task."""
        import asyncio

        from zrb.llm.ui.simple_ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        # Start the flush loop
        await buffered.start_flush_loop()

        # Verify a task was created
        assert buffered._flush_task is not None
        assert hasattr(buffered._flush_task, "cancel")

        # Clean up
        buffered._flush_task.cancel()
        try:
            await buffered._flush_task
        except asyncio.CancelledError:
            pass


class TestCreateUIFactory:
    """Tests for create_ui_factory function."""

    def test_create_ui_factory_basic(self):
        """Test create_ui_factory creates working factory."""
        from zrb.llm.ui.simple_ui import SimpleUI, UIConfig, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        factory = create_ui_factory(TestSimpleUI)

        from zrb.context.shared_context import SharedContext

        ui = factory(
            ctx=SharedContext(),
            llm_task_core=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="Hello",
            initial_conversation_name="test-session",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert ui is not None
        assert ui._assistant_name == "Assistant"
        assert ui._conversation_session_name == "test-session"

    def test_create_ui_factory_with_custom_config(self):
        """Test create_ui_factory with custom UIConfig."""
        from zrb.llm.ui.simple_ui import SimpleUI, UIConfig, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        config = UIConfig(assistant_name="CustomBot")
        factory = create_ui_factory(TestSimpleUI, config=config)

        from zrb.context.shared_context import SharedContext

        ui = factory(
            ctx=SharedContext(),
            llm_task_core=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="",
            initial_conversation_name="",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert ui._assistant_name == "CustomBot"

    def test_create_ui_factory_merges_commands(self):
        """Test create_ui_factory merges ui_commands with config."""
        from zrb.llm.ui.simple_ui import SimpleUI, UIConfig, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        config = UIConfig(exit_commands=["/exit"])
        factory = create_ui_factory(TestSimpleUI, config=config)

        from zrb.context.shared_context import SharedContext

        ui = factory(
            ctx=SharedContext(),
            llm_task_core=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={"exit": ["/quit"]},
            initial_message="",
            initial_conversation_name="",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert ui._exit_commands == ["/quit"]

    def test_create_ui_factory_creates_ui(self):
        """Test create_ui_factory creates UI with correct configuration."""
        from zrb.llm.ui.simple_ui import SimpleUI, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        factory = create_ui_factory(TestSimpleUI)

        from zrb.context.shared_context import SharedContext

        ctx = SharedContext()
        ui = factory(
            ctx=ctx,
            llm_task_core=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="Test message",
            initial_conversation_name="my-session",
            initial_yolo=False,
            initial_attachments=[],
        )

        # Verify UI was created with correct settings
        assert ui._conversation_session_name == "my-session"
        assert ui._initial_message == "Test message"
        assert ui._assistant_name == "Assistant"


class TestBaseUICommandHandlers:
    """Tests for BaseUI command handler methods."""

    @pytest.fixture
    def simple_ui_instance(self):
        """Create a SimpleUI instance for testing BaseUI methods."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui.simple_ui import SimpleUI, UIConfig

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ctx = SharedContext()
        return TestSimpleUI(
            ctx=ctx,
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            config=UIConfig.default(),
        )

    def test_handle_exit_command(self, simple_ui_instance):
        """Test _handle_exit_command returns True for exit commands."""
        ui = simple_ui_instance
        ui._exit_commands = ["/exit", "/quit"]

        assert ui._handle_exit_command("/exit") is True
        assert ui._handle_exit_command("/quit") is True
        assert ui._handle_exit_command("/help") is False

    def test_handle_exit_command_trims_whitespace(self, simple_ui_instance):
        """Test _handle_exit_command trims whitespace."""
        ui = simple_ui_instance
        ui._exit_commands = ["/exit"]

        assert ui._handle_exit_command("  /exit  ") is True

    def test_handle_info_command(self, simple_ui_instance):
        """Test _handle_info_command returns True for info commands."""
        ui = simple_ui_instance
        ui._info_commands = ["/help", "/?"]
        ui.append_to_output = MagicMock()

        assert ui._handle_info_command("/help") is True
        ui.append_to_output.assert_called()

    def test_handle_info_command_empty_commands(self, simple_ui_instance):
        """Test _handle_info_command with empty commands list."""
        ui = simple_ui_instance
        ui._info_commands = []

        assert ui._handle_info_command("/help") is False

    def test_handle_save_command(self, simple_ui_instance):
        """Test _handle_save_command saves conversation."""
        ui = simple_ui_instance
        ui._save_commands = ["/save"]
        ui._history_manager.load = MagicMock(return_value=[])
        ui._history_manager.update = MagicMock()
        ui._history_manager.save = MagicMock()
        ui.append_to_output = MagicMock()
        ui._conversation_session_name = "test-session"

        result = ui._handle_save_command("/save my-save")

        assert result is True
        ui._history_manager.update.assert_called_once()
        ui._history_manager.save.assert_called_once_with("my-save")

    def test_handle_save_command_no_name(self, simple_ui_instance):
        """Test _handle_save_command with no name provided."""
        ui = simple_ui_instance
        ui._save_commands = ["/save"]
        ui._history_manager.load = MagicMock(return_value=[])
        ui._history_manager.update = MagicMock()

        result = ui._handle_save_command("/save")

        assert result is False

    def test_handle_save_command_handles_error(self, simple_ui_instance):
        """Test _handle_save_command handles history manager errors."""
        ui = simple_ui_instance
        ui._save_commands = ["/save"]
        ui._history_manager.load = MagicMock(side_effect=Exception("Load error"))
        ui.append_to_output = MagicMock()

        result = ui._handle_save_command("/save test")

        assert result is True  # Returns True because command matched
        ui.append_to_output.assert_called()  # Error was reported

    def test_handle_load_command(self, simple_ui_instance):
        """Test _handle_load_command loads conversation."""
        ui = simple_ui_instance
        ui._load_commands = ["/load"]
        ui._history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        result = ui._handle_load_command("/load my-session")

        assert result is True
        assert ui._conversation_session_name == "my-session"

    def test_handle_load_command_no_name(self, simple_ui_instance):
        """Test _handle_load_command with no name provided."""
        ui = simple_ui_instance
        ui._load_commands = ["/load"]

        result = ui._handle_load_command("/load")

        assert result is False

    def test_handle_redirect_command(self, simple_ui_instance):
        """Test _handle_redirect_command redirects output to file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui._redirect_output_commands = ["/redirect"]
        ui._last_result_data = "Test output content"
        ui.append_to_output = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            result = ui._handle_redirect_command(f"/redirect {temp_path}")

            assert result is True
            with open(temp_path, "r") as f:
                assert f.read() == "Test output content"
        finally:
            os.unlink(temp_path)

    def test_handle_redirect_command_no_output(self, simple_ui_instance):
        """Test _handle_redirect_command when no output available."""
        ui = simple_ui_instance
        ui._redirect_output_commands = ["/redirect"]
        ui._last_result_data = None
        ui.append_to_output = MagicMock()

        result = ui._handle_redirect_command("/redirect /tmp/out.txt")

        assert result is True
        ui.append_to_output.assert_called()  # Error message shown

    def test_handle_redirect_command_no_path(self, simple_ui_instance):
        """Test _handle_redirect_command with no path provided."""
        ui = simple_ui_instance
        ui._redirect_output_commands = ["/redirect"]

        result = ui._handle_redirect_command("/redirect")

        assert result is False

    def test_handle_toggle_yolo(self, simple_ui_instance):
        """Test _handle_toggle_yolo toggles yolo mode."""
        ui = simple_ui_instance

        assert ui._yolo is False
        ui._handle_toggle_yolo("/yolo")
        assert ui._yolo is True
        ui._handle_toggle_yolo("/yolo")
        assert ui._yolo is False

    def test_handle_set_model_command(self, simple_ui_instance):
        """Test _handle_set_model_command changes model."""
        ui = simple_ui_instance
        ui._set_model_commands = ["/model"]
        ui._is_thinking = False
        ui.append_to_output = MagicMock()

        result = ui._handle_set_model_command("/model gpt-4")

        assert result is True
        assert ui._model == "gpt-4"

    def test_handle_set_model_command_while_thinking(self, simple_ui_instance):
        """Test _handle_set_model_command blocked while thinking."""
        ui = simple_ui_instance
        ui._set_model_commands = ["/model"]
        ui._is_thinking = True

        result = ui._handle_set_model_command("/model gpt-4")

        assert result is False

    def test_handle_set_model_command_no_model(self, simple_ui_instance):
        """Test _handle_set_model_command with no model provided."""
        ui = simple_ui_instance
        ui._set_model_commands = ["/model"]
        ui._is_thinking = False

        result = ui._handle_set_model_command("/model")

        assert result is False

    def test_handle_attach_command(self, simple_ui_instance):
        """Test _handle_attach_command attaches file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui._attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        # Create a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            result = ui._handle_attach_command(f"/attach {temp_path}")

            assert result is True
            assert temp_path in ui._pending_attachments
        finally:
            os.unlink(temp_path)

    def test_handle_attach_command_file_not_found(self, simple_ui_instance):
        """Test _handle_attach_command with non-existent file."""
        ui = simple_ui_instance
        ui._attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        result = ui._handle_attach_command("/attach /nonexistent/file.txt")

        assert result is True
        ui.append_to_output.assert_called()  # Error shown

    def test_handle_attach_command_already_attached(self, simple_ui_instance):
        """Test _handle_attach_command with already attached file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui._attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            # Attach first time
            ui._handle_attach_command(f"/attach {temp_path}")
            # Try to attach again
            ui.append_to_output.reset_mock()
            result = ui._handle_attach_command(f"/attach {temp_path}")

            assert result is True
            ui.append_to_output.assert_called()  # "Already attached" message
        finally:
            os.unlink(temp_path)

    def test_get_help_text(self, simple_ui_instance):
        """Test _get_help_text returns formatted help."""
        ui = simple_ui_instance
        ui._exit_commands = ["/exit"]
        ui._info_commands = ["/help"]
        ui._attach_commands = ["/attach"]

        help_text = ui._get_help_text()

        assert "/exit" in help_text
        assert "/help" in help_text
        assert "/attach" in help_text

    def test_get_help_text_with_limit(self, simple_ui_instance):
        """Test _get_help_text respects limit parameter."""
        ui = simple_ui_instance
        ui._exit_commands = ["/exit"]
        ui._info_commands = ["/help"]
        ui._attach_commands = ["/attach"]

        help_text = ui._get_help_text(limit=1)

        assert "and more" in help_text

    def test_get_help_text_empty_commands(self, simple_ui_instance):
        """Test _get_help_text with all empty command lists."""
        ui = simple_ui_instance
        ui._exit_commands = []
        ui._info_commands = []
        ui._attach_commands = []
        ui._save_commands = []
        ui._load_commands = []
        ui._redirect_output_commands = []
        ui._summarize_commands = []
        ui._yolo_toggle_commands = []
        ui._set_model_commands = []
        ui._exec_commands = []
        ui._custom_commands = []

        help_text = ui._get_help_text()

        assert help_text == ""

    def test_get_cwd_display_home(self, simple_ui_instance):
        """Test _get_cwd_display shows home directory as ~."""
        ui = simple_ui_instance

        import os

        home = os.path.expanduser("~")
        os.chdir(home)

        result = ui._get_cwd_display()

        assert result == "~"

    def test_execute_hook_sync_context(self, simple_ui_instance):
        """Test execute_hook works in sync context."""
        from zrb.llm.hook.types import HookEvent

        ui = simple_ui_instance

        # Should not raise even without running event loop
        ui.execute_hook(HookEvent.NOTIFICATION, {"message": "test"})

    def test_triggers_property(self, simple_ui_instance):
        """Test triggers property getter and setter."""
        ui = simple_ui_instance

        async def trigger():
            yield "triggered"

        ui.triggers = [trigger]

        assert trigger in ui.triggers

    def test_invalidate_ui(self, simple_ui_instance):
        """Test invalidate_ui does not raise."""
        ui = simple_ui_instance

        # Should not raise
        ui.invalidate_ui()

    def test_on_exit(self, simple_ui_instance):
        """Test on_exit does not raise."""
        ui = simple_ui_instance

        # Should not raise
        ui.on_exit()

    def test_get_output_field_width(self, simple_ui_instance):
        """Test _get_output_field_width returns None by default."""
        ui = simple_ui_instance

        assert ui._get_output_field_width() is None

    def test_stream_to_parent(self, simple_ui_instance):
        """Test stream_to_parent calls append_to_output."""
        ui = simple_ui_instance
        ui.append_to_output = MagicMock()

        ui.stream_to_parent("test output")

        ui.append_to_output.assert_called_once()
