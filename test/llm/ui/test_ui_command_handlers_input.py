from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBaseUIInputCommands:
    """Tests for BaseUI command handler methods."""

    @pytest.fixture
    def simple_ui_instance(self):
        """Create a SimpleUI instance for testing BaseUI methods."""
        from zrb.context.context import Context
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import SimpleUI, UIConfig

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ctx = Context(SharedContext(), "test", 0, "")
        return TestSimpleUI(
            ctx=ctx,
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            config=UIConfig.default(),
        )

    def test_handle_toggle_yolo(self, simple_ui_instance):
        """Test _handle_toggle_yolo toggles yolo mode."""
        ui = simple_ui_instance

        assert ui.yolo is False
        ui.handle_toggle_yolo("/yolo")
        assert ui.yolo is True
        ui.handle_toggle_yolo("/yolo")
        assert ui.yolo is False

    def test_handle_set_model_command(self, simple_ui_instance):
        """Test _handle_set_model_command changes model."""
        ui = simple_ui_instance
        ui.set_model_commands = ["/model"]
        ui.is_thinking = False
        ui.append_to_output = MagicMock()

        result = ui.handle_set_model_command("/model gpt-4")

        assert result is True
        assert ui.model == "gpt-4"

    def test_handle_set_model_command_while_thinking(self, simple_ui_instance):
        """Test _handle_set_model_command blocked while thinking."""
        ui = simple_ui_instance
        ui.set_model_commands = ["/model"]
        ui.is_thinking = True

        result = ui.handle_set_model_command("/model gpt-4")

        assert result is False

    def test_handle_set_model_command_no_model(self, simple_ui_instance):
        """Test _handle_set_model_command with no model provided."""
        ui = simple_ui_instance
        ui.set_model_commands = ["/model"]
        ui.is_thinking = False

        result = ui.handle_set_model_command("/model")

        assert result is False

    def test_handle_attach_command(self, simple_ui_instance):
        """Test _handle_attach_command attaches file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        # Create a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            result = ui.handle_attach_command(f"/attach {temp_path}")

            assert result is True
            assert temp_path in ui.pending_attachments
        finally:
            os.unlink(temp_path)

    def test_handle_attach_command_file_not_found(self, simple_ui_instance):
        """Test _handle_attach_command with non-existent file."""
        ui = simple_ui_instance
        ui.attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        result = ui.handle_attach_command("/attach /nonexistent/file.txt")

        assert result is True
        ui.append_to_output.assert_called()  # Error shown

    def test_handle_attach_command_already_attached(self, simple_ui_instance):
        """Test _handle_attach_command with already attached file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            # Attach first time
            ui.handle_attach_command(f"/attach {temp_path}")
            # Try to attach again
            ui.append_to_output.reset_mock()
            result = ui.handle_attach_command(f"/attach {temp_path}")

            assert result is True
            ui.append_to_output.assert_called()  # "Already attached" message
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_handle_photo_command_captures_and_attaches(self, simple_ui_instance):
        """Test _handle_photo_command captures a photo and attaches it."""
        ui = simple_ui_instance
        ui.photo_commands = ["/photo"]
        ui.append_to_output = MagicMock()

        with patch(
            "zrb.llm.ui.base.conversation_commands.get_camera_photo",
            new=AsyncMock(return_value=b"\xff\xd8\xff-fake-jpeg"),
        ):
            result = ui.handle_photo_command("/photo")

            assert result is True
            assert len(ui.background_tasks) == 1
            task = list(ui.background_tasks)[0]
            await task

        assert len(ui.pending_attachments) == 1

    @pytest.mark.asyncio
    async def test_handle_photo_command_capture_failure(self, simple_ui_instance):
        """Test _handle_photo_command shows an error when capture fails."""
        ui = simple_ui_instance
        ui.photo_commands = ["/photo"]
        ui.append_to_output = MagicMock()

        with patch(
            "zrb.llm.ui.base.conversation_commands.get_camera_photo",
            new=AsyncMock(return_value=None),
        ):
            result = ui.handle_photo_command("/photo")

            task = list(ui.background_tasks)[0]
            await task

        assert result is True
        assert ui.pending_attachments == []
        ui.append_to_output.assert_called()
