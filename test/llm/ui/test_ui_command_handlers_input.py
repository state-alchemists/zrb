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

    def test_handle_toggle_sandbox(self, simple_ui_instance, monkeypatch):
        """`/sandbox` flips this session's switch, both ways."""
        from zrb.config.config import CFG

        ui = simple_ui_instance
        ui.append_to_output = MagicMock()
        monkeypatch.setattr(CFG, "LLM_SANDBOX_ENABLED", False)

        assert ui.handle_toggle_sandbox("/sandbox") is True
        assert ui.sandbox_override is True

        assert ui.handle_toggle_sandbox("/sandbox") is True
        assert ui.sandbox_override is False
        # The deployment's setting is not a conversation's to rewrite.
        assert CFG.LLM_SANDBOX_ENABLED is False

    def test_handle_toggle_sandbox_accepts_a_named_state(
        self, simple_ui_instance, monkeypatch
    ):
        """`/sandbox on` is not a flip: saying it twice leaves it on."""
        from zrb.config.config import CFG

        ui = simple_ui_instance
        ui.append_to_output = MagicMock()
        monkeypatch.setattr(CFG, "LLM_SANDBOX_ENABLED", False)

        assert ui.handle_toggle_sandbox("/sandbox on") is True
        assert ui.sandbox_override is True
        assert ui.handle_toggle_sandbox("/sandbox ON") is True
        assert ui.sandbox_override is True
        assert ui.handle_toggle_sandbox("/sandbox off") is True
        assert ui.sandbox_override is False

    def test_handle_toggle_sandbox_ignores_an_unknown_argument(
        self, simple_ui_instance, monkeypatch
    ):
        """An argument that is neither `on` nor `off` is not consumed."""
        from zrb.config.config import CFG

        ui = simple_ui_instance
        monkeypatch.setattr(CFG, "LLM_SANDBOX_ENABLED", False)

        assert ui.handle_toggle_sandbox("/sandbox maybe") is False
        assert ui.sandbox_override is None

    def test_sandbox_off_beats_a_deployment_that_turned_it_on(
        self, simple_ui_instance, monkeypatch
    ):
        """The session's word is the last one: `off` wins over the config."""
        from zrb.config.config import CFG
        from zrb.llm.sandbox.state import get_effective_sandbox_policy
        from zrb.llm.shared.agent_state import current_ui

        ui = simple_ui_instance
        ui.append_to_output = MagicMock()
        monkeypatch.setattr(CFG, "LLM_SANDBOX_ENABLED", True)

        token = current_ui.set(ui)
        try:
            assert get_effective_sandbox_policy().enabled is True
            assert ui.handle_toggle_sandbox("/sandbox off") is True
            assert get_effective_sandbox_policy().enabled is False
        finally:
            current_ui.reset(token)

    def test_sandbox_runs_while_the_model_is_thinking(self, simple_ui_instance):
        """Flipping it mid-turn is the point, so it is not held back."""
        assert simple_ui_instance.classify_input("/sandbox") == "thinking_command"

    def test_an_invalid_sandbox_argument_is_a_message_not_a_refusal(
        self, simple_ui_instance
    ):
        """`/sandbox maybe` is the user's text, not a command that refuses.

        The token is a prefix because it takes `on` and `off`, so every line
        beginning with it was classified as runnable mid-turn. Mid-turn, the
        handler then refused it and the refusal notice stood where the message
        should have been queued.
        """
        ui = simple_ui_instance

        assert ui.classify_input("/sandbox maybe") == "message"
        assert ui.classify_input("/sandbox on now") == "message"
        assert ui.classify_input("/sandbox on") == "thinking_command"
        assert ui.classify_input("/plan xyz") == "message"

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
