from unittest.mock import MagicMock, patch

import pytest


class TestBaseUIOutputCommands:
    """Tests for BaseUI command handler methods."""

    @pytest.fixture
    def simple_ui_instance(self):
        """Create a SimpleUI instance for testing BaseUI methods."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import SimpleUI, UIConfig

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
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

    def test_handle_redirect_command(self, simple_ui_instance):
        """Test _handle_redirect_command redirects output to file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = "Test output content"
        ui.append_to_output = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            result = ui.handle_redirect_command(f"/redirect {temp_path}")

            assert result is True
            with open(temp_path, "r") as f:
                assert f.read() == "Test output content"
        finally:
            os.unlink(temp_path)

    def test_handle_redirect_command_no_output(self, simple_ui_instance):
        """Test _handle_redirect_command when no output available."""
        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = None
        ui.append_to_output = MagicMock()

        result = ui.handle_redirect_command("/redirect /tmp/out.txt")

        assert result is True
        ui.append_to_output.assert_called()  # Error message shown

    def test_handle_redirect_command_clipboard(self, simple_ui_instance):
        """Test _handle_redirect_command bare command copies output to clipboard."""
        from unittest.mock import patch

        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = "Test AI output"
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
            result = ui.handle_redirect_command("/redirect")

        assert result is True
        mock_copy.assert_called_once_with("Test AI output")

    def test_handle_redirect_command_bare_no_output(self, simple_ui_instance):
        """Test bare /redirect shows error when no output available."""
        from unittest.mock import patch

        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = None
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.util.clipboard.copy_text") as mock_copy:
            result = ui.handle_redirect_command("/redirect")

        assert result is True
        mock_copy.assert_not_called()
        ui.append_to_output.assert_called()  # Error shown

    def test_handle_copy_command(self, simple_ui_instance):
        """Test bare /copy copies full transcript to clipboard."""
        from unittest.mock import patch

        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(
            return_value=[{"role": "user", "content": "hi"}]
        )
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
            with patch(
                "zrb.llm.util.history_formatter.format_history_as_text",
                return_value="transcript",
            ):
                result = ui.handle_copy_command("/copy")

        assert result is True
        mock_copy.assert_called_once_with("transcript")

    def test_handle_copy_command_to_file(self, simple_ui_instance):
        """Test /copy with path writes transcript to file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(
            return_value=[{"role": "user", "content": "hi"}]
        )
        ui.append_to_output = MagicMock()

        with patch(
            "zrb.llm.util.history_formatter.format_history_as_text",
            return_value="transcript content",
        ):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
                temp_path = f.name

            try:
                result = ui.handle_copy_command(f"/copy {temp_path}")
                assert result is True
                with open(temp_path) as f:
                    assert f.read() == "transcript content"
            finally:
                os.unlink(temp_path)

    def test_handle_copy_command_no_history(self, simple_ui_instance):
        """Test /copy shows error when no history."""
        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        result = ui.handle_copy_command("/copy")

        assert result is True
        ui.append_to_output.assert_called()  # Error shown

    def test_handle_copy_command_trailing_space_strips_to_bare(
        self, simple_ui_instance
    ):
        """Test /copy with a trailing space strips to the bare command (clipboard copy)."""
        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        result = ui.handle_copy_command("/copy ")

        assert result is True  # stripped to bare /copy

    def test_handle_copy_command_unrecognized(self, simple_ui_instance):
        """Test /copy with an unrecognized command returns False."""
        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]

        result = ui.handle_copy_command("/notcopy")

        assert result is False
