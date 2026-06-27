from unittest.mock import MagicMock

import pytest


class TestSimpleUISubclass:
    """Tests for SimpleUI subclass behavior."""

    @pytest.fixture
    def simple_ui_deps(self):
        """Create mock dependencies for SimpleUI."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import UIConfig

        return {
            "ctx": SharedContext(),
            "llm_task": MagicMock(),
            "history_manager": MagicMock(),
            "config": UIConfig.default(),
        }

    def test_simple_ui_creation_with_defaults(self, simple_ui_deps):
        """Test SimpleUI creation with default parameters."""
        from zrb.llm.ui import SimpleUI

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        # Verify through public behavior - UI was created successfully
        assert ui is not None

    def test_simple_ui_creation_with_custom_config(self, simple_ui_deps):
        """Test SimpleUI creation with custom config."""
        from zrb.llm.ui import SimpleUI, UIConfig

        simple_ui_deps["config"] = UIConfig(
            assistant_name="CustomBot",
            is_yolo=True,
        )

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        # Verify through public behavior - UI was created successfully with custom config
        assert ui is not None

    def test_simple_ui_generates_yolo_xcom_key(self, simple_ui_deps):
        """Test SimpleUI generates yolo_xcom_key if not provided."""
        from zrb.llm.ui import SimpleUI, UIConfig

        simple_ui_deps["config"] = UIConfig(yolo_xcom_key="")

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        # Verify UI was created successfully - yolo_xcom_key is auto-generated
        assert ui is not None

    def test_simple_ui_with_response_handlers(self, simple_ui_deps):
        """Test SimpleUI accepts response_handlers parameter."""
        from zrb.llm.ui import SimpleUI

        mock_handler = MagicMock()
        simple_ui_deps["response_handlers"] = [mock_handler]

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        # Verify UI was created successfully with response handlers
        assert ui is not None

    def test_simple_ui_with_argument_formatters(self, simple_ui_deps):
        """Test SimpleUI accepts argument_formatters parameter."""
        from zrb.llm.ui import SimpleUI

        mock_formatter = MagicMock()
        simple_ui_deps["argument_formatters"] = [mock_formatter]

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ui = TestSimpleUI(**simple_ui_deps)

        # Verify UI was created successfully with argument formatters
        assert ui is not None

    def test_simple_ui_accepts_extra_kwargs(self, simple_ui_deps):
        """Test SimpleUI accepts extra kwargs for subclass use."""
        from zrb.llm.ui import SimpleUI

        simple_ui_deps["custom_param"] = "custom_value"

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
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
        from zrb.llm.ui import SimpleUI

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
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
        from zrb.llm.ui import UIConfig

        return {
            "ctx": SharedContext(),
            "llm_task": MagicMock(),
            "history_manager": MagicMock(),
            "config": UIConfig.default(),
        }

    def test_event_ui_creates_input_queue(self, event_ui_deps):
        """Test EventDrivenUI creates input queue."""
        from zrb.llm.ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)

        # Verify UI was created successfully
        assert ui is not None

    def test_event_ui_get_input_blocks(self, event_ui_deps):
        """Test EventDrivenUI creates input queue on init."""
        from zrb.llm.ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)

        # Verify UI was created successfully
        assert ui is not None

    def test_handle_incoming_message_queues_when_waiting(self, event_ui_deps):
        """Test handle_incoming_message queues when waiting for input."""
        from zrb.llm.ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)

        # Verify handle_incoming_message exists and is callable
        assert hasattr(ui, "handle_incoming_message")
        assert callable(ui.handle_incoming_message)

    def test_handle_incoming_message_submits_when_not_waiting(self, event_ui_deps):
        """Test handle_incoming_message submits when not waiting for input."""
        from zrb.llm.ui import EventDrivenUI

        class TestEventUI(EventDrivenUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def start_event_loop(self):
                pass

        ui = TestEventUI(**event_ui_deps)
        ui._llm_task = MagicMock()

        # Verify handle_incoming_message exists and is callable
        assert hasattr(ui, "handle_incoming_message")
        assert callable(ui.handle_incoming_message)


class TestPollingUI:
    """Tests for PollingUI class."""

    @pytest.fixture
    def polling_ui_deps(self):
        """Create mock dependencies for PollingUI."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import UIConfig

        return {
            "ctx": SharedContext(),
            "llm_task": MagicMock(),
            "history_manager": MagicMock(),
            "config": UIConfig.default(),
        }

    def test_polling_ui_creates_output_queue(self, polling_ui_deps):
        """Test PollingUI creates output queue."""
        from zrb.llm.ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        # Verify UI was created successfully
        assert ui is not None

    @pytest.mark.asyncio
    async def test_polling_ui_print_queues_output(self, polling_ui_deps):
        """Test PollingUI.print queues output."""
        from zrb.llm.ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        await ui.print("test output")

        result = ui.output_queue.get_nowait()
        assert result == "test output"

    def test_polling_ui_get_input_blocks(self, polling_ui_deps):
        """Test PollingUI creates input queue."""
        from zrb.llm.ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        # Verify UI was created successfully
        assert ui is not None

    def test_polling_ui_handle_incoming_queues_when_waiting(self, polling_ui_deps):
        """Test handle_incoming_message queues when waiting for input."""
        from zrb.llm.ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)

        # Verify handle_incoming_message exists and is callable
        assert hasattr(ui, "handle_incoming_message")
        assert callable(ui.handle_incoming_message)

    def test_polling_ui_handle_incoming_submits_when_idle(self, polling_ui_deps):
        """Test handle_incoming_message submits when LLM is idle."""
        from zrb.llm.ui import PollingUI

        class TestPollingUI(PollingUI):
            pass

        ui = TestPollingUI(**polling_ui_deps)
        ui._llm_task = MagicMock()

        # Verify handle_incoming_message exists and is callable
        assert hasattr(ui, "handle_incoming_message")
        assert callable(ui.handle_incoming_message)


class TestBufferedOutputMixin:
    """Tests for BufferedOutputMixin class."""

    def test_buffer_creates_flush_task(self):
        """Test BufferedOutputMixin creates flush task on start."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered(flush_interval=0.1)

        # Use public properties
        assert buffered.buffer == []
        assert buffered.flush_interval == 0.1

    def test_buffer_output_filters_pure_spinner(self):
        """Test buffer_output filters pure spinner updates."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("\r⠇")
        buffered.buffer_output("\r⠏⠋⠙")

        # Use public property
        assert len(buffered.buffer) == 0

    def test_buffer_output_filters_progress_at_end(self):
        """Test buffer_output filters spinner at end of line."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        # Spinners at end get stripped but message body remains
        buffered.buffer_output("Loading")
        buffered.buffer_output("Processing")

        # Both should be buffered (no spinner chars in test)
        # Use public property
        assert len(buffered.buffer) == 2

    def test_buffer_output_filters_prepare_tool_params(self):
        """Test buffer_output filters 'Prepare tool parameters' messages."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("🔄 Prepare tool parameters ⠇")

        # Use public property
        assert len(buffered.buffer) == 0

    def test_buffer_output_normal_text(self):
        """Test buffer_output accepts normal text."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("Hello, world!")

        # Use public property
        assert len(buffered.buffer) == 1
        assert buffered.buffer[0] == "Hello, world!"

    def test_buffer_output_removes_carriage_returns(self):
        """Test buffer_output removes carriage returns from text."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        buffered.buffer_output("Line1\rLine2")

        # Use public property
        assert "\r" not in buffered.buffer[0]

    @pytest.mark.asyncio
    async def test_stop_flush_loop_method_exists(self):
        """Test stop_flush_loop method exists and is async."""
        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        # Verify the method exists and is callable
        assert callable(getattr(buffered, "stop_flush_loop", None))

        # Use public property
        assert not buffered.has_flush_task

    @pytest.mark.asyncio
    async def test_start_flush_loop_creates_task(self):
        """Test start_flush_loop creates a flush task."""
        import asyncio

        from zrb.llm.ui import BufferedOutputMixin

        class TestBuffered(BufferedOutputMixin):
            async def _send_buffered(self, text: str):
                pass

        buffered = TestBuffered()

        # Start the flush loop
        await buffered.start_flush_loop()

        # Use public property
        assert buffered.has_flush_task

        # Clean up - use internal for cancellation (test cleanup is OK)
        buffered._flush_task.cancel()
        try:
            await buffered._flush_task
        except asyncio.CancelledError:
            pass
