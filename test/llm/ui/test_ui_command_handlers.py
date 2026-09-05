from unittest.mock import MagicMock

import pytest


class TestBaseUICommandHandlers:
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

    def test_handle_exit_command(self, simple_ui_instance):
        """Test _handle_exit_command returns True for exit commands."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit", "/quit"]

        assert ui.handle_exit_command("/exit") is True
        assert ui.handle_exit_command("/quit") is True
        assert ui.handle_exit_command("/help") is False

    def test_handle_exit_command_trims_whitespace(self, simple_ui_instance):
        """Test _handle_exit_command trims whitespace."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit"]

        assert ui.handle_exit_command("  /exit  ") is True

    def test_handle_info_command(self, simple_ui_instance):
        """Test _handle_info_command returns True for info commands."""
        ui = simple_ui_instance
        ui.info_commands = ["/help", "/?"]
        ui.append_to_output = MagicMock()

        assert ui.handle_info_command("/help") is True
        ui.append_to_output.assert_called()

    def test_handle_info_command_empty_commands(self, simple_ui_instance):
        """Test _handle_info_command with empty commands list."""
        ui = simple_ui_instance
        ui.info_commands = []

        assert ui.handle_info_command("/help") is False

    def test_handle_save_command(self, simple_ui_instance):
        """Test _handle_save_command saves conversation."""
        ui = simple_ui_instance
        ui.save_commands = ["/save"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.history_manager.update = MagicMock()
        ui.history_manager.save = MagicMock()
        ui.append_to_output = MagicMock()
        ui.conversation_session_name = "test-session"

        result = ui.handle_save_command("/save my-save")

        assert result is True
        ui.history_manager.update.assert_called_once()
        ui.history_manager.save.assert_called_once_with("my-save")

    def test_handle_save_command_no_name(self, simple_ui_instance):
        """Bare `/save` warns instead of falling through to the LLM."""
        ui = simple_ui_instance
        ui.save_commands = ["/save"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.history_manager.update = MagicMock()
        ui.append_to_output = MagicMock()

        result = ui.handle_save_command("/save")

        assert result is True
        assert any(
            "Conversation name required" in str(call)
            for call in ui.append_to_output.call_args_list
        )

    def test_handle_save_command_handles_error(self, simple_ui_instance):
        """Test _handle_save_command handles history manager errors."""
        ui = simple_ui_instance
        ui.save_commands = ["/save"]
        ui.history_manager.load = MagicMock(side_effect=Exception("Load error"))
        ui.append_to_output = MagicMock()

        result = ui.handle_save_command("/save test")

        assert result is True  # Returns True because command matched
        ui.append_to_output.assert_called()  # Error was reported

    def test_handle_load_command(self, simple_ui_instance):
        """Test _handle_load_command loads conversation."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()
        ui.accumulate_usage(MagicMock(input_tokens=100, output_tokens=50))

        result = ui.handle_load_command("/load my-session")

        assert result is True
        assert ui.conversation_session_name == "my-session"
        # The usage meter tracks spend per loaded conversation
        assert ui.session_token_usage == (0, 0)

    def test_handle_load_command_no_name(self, simple_ui_instance):
        """Bare `/load` warns instead of falling through to the LLM."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.append_to_output = MagicMock()
        ui.conversation_session_name = "current-session"

        result = ui.handle_load_command("/load")

        assert result is True
        assert any(
            "Conversation name required" in str(call)
            for call in ui.append_to_output.call_args_list
        )
        # The session name must be untouched.
        assert ui.conversation_session_name == "current-session"

    def test_handle_load_command_no_name_alias_and_whitespace(self, simple_ui_instance):
        """/resume and a trailing space hit the same warning path."""
        ui = simple_ui_instance
        ui.load_commands = ["/load", "/resume"]
        ui.append_to_output = MagicMock()

        assert ui.handle_load_command("  /resume  ") is True
        assert ui.handle_load_command("/load ") is True
        assert ui.append_to_output.call_count == 2

    def test_get_help_text(self, simple_ui_instance):
        """Test _get_help_text returns formatted help."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit"]
        ui.info_commands = ["/help"]
        ui.attach_commands = ["/attach"]

        help_text = ui.get_help_text()

        assert "/exit" in help_text
        assert "/help" in help_text
        assert "/attach" in help_text
        assert "Keyboard Shortcuts:" in help_text
        assert "Ctrl+J" in help_text
        assert "Ctrl+V / Alt+V" in help_text
        assert "Ctrl+K" in help_text
        assert "Shift+Tab" in help_text

    def test_get_help_text_lists_every_command_at_any_width(self, simple_ui_instance):
        """No command is dropped and no description clipped, however narrow."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit"]
        ui.info_commands = ["/help"]
        ui.attach_commands = ["/attach"]

        for width in (200, 100, 50):
            help_text = ui.get_help_text(width=width)
            assert "and more" not in help_text
            assert "..." not in help_text
            for expected in ("/exit", "/help", "/attach", "clipboard"):
                assert expected in help_text

    def test_get_help_text_empty_commands(self, simple_ui_instance):
        """Test _get_help_text with all empty command lists."""
        ui = simple_ui_instance
        ui.exit_commands = []
        ui.info_commands = []
        ui.attach_commands = []
        ui.photo_commands = []
        ui.save_commands = []
        ui.load_commands = []
        ui.redirect_output_commands = []
        ui.summarize_commands = []
        ui.yolo_toggle_commands = []
        ui.set_model_commands = []
        ui.exec_commands = []
        ui.plan_commands = []
        ui.copy_commands = []
        ui.btw_commands = []
        ui.voice_commands = []
        ui.custom_commands = []

        help_text = ui.get_help_text()

        assert help_text == ""

    def test_get_cwd_display_home(self, simple_ui_instance, monkeypatch):
        """Test get_cwd_display shows home directory as ~."""
        ui = simple_ui_instance

        import os

        # monkeypatch restores the original cwd on teardown — an unrestored
        # os.chdir() here would leak into every test that runs afterward,
        # depending on collection order to avoid ever being noticed.
        monkeypatch.chdir(os.path.expanduser("~"))

        result = ui.get_cwd_display()

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
        """Test output_field_width returns None by default."""
        ui = simple_ui_instance

        assert ui.output_field_width is None

    def test_stream_to_parent(self, simple_ui_instance):
        """Test stream_to_parent calls append_to_output."""
        ui = simple_ui_instance
        ui.append_to_output = MagicMock()

        ui.stream_to_parent("test output")

        ui.append_to_output.assert_called_once()
