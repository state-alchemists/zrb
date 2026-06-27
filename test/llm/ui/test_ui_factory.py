from unittest.mock import MagicMock

from zrb.llm.ui import UIConfig


class TestUIConfig:
    """Tests for UIConfig dataclass."""

    def test_default_config(self):
        """Test UIConfig.default() creates default config."""

        config = UIConfig.default()

        assert config.assistant_name == "Assistant"
        assert "/exit" in config.exit_commands
        assert "/help" in config.info_commands

    def test_minimal_config(self):
        """Test UIConfig.minimal() creates minimal config."""

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

        config = UIConfig(
            assistant_name="MyBot",
            is_yolo=True,
            conversation_session_name="my-session",
        )

        assert config.assistant_name == "MyBot"
        assert config.is_yolo is True
        assert config.conversation_session_name == "my-session"


class TestCreateUIFactory:
    """Tests for create_ui_factory function."""

    def test_create_ui_factory_basic(self):
        """Test create_ui_factory creates working factory."""
        from zrb.llm.ui import SimpleUI, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        factory = create_ui_factory(TestSimpleUI)

        from zrb.context.shared_context import SharedContext

        ui = factory(
            ctx=SharedContext(),
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="Hello",
            initial_conversation_name="test-session",
            initial_yolo=False,
            initial_attachments=[],
        )

        # Use public properties
        assert ui is not None
        assert ui.assistant_name == "Assistant"
        assert ui.conversation_session_name == "test-session"

    def test_create_ui_factory_with_custom_config(self):
        """Test create_ui_factory with custom UIConfig."""
        from zrb.llm.ui import SimpleUI, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        config = UIConfig(assistant_name="CustomBot")
        factory = create_ui_factory(TestSimpleUI, config=config)

        from zrb.context.shared_context import SharedContext

        ui = factory(
            ctx=SharedContext(),
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="",
            initial_conversation_name="",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert ui.assistant_name == "CustomBot"

    def test_create_ui_factory_merges_commands(self):
        """Test create_ui_factory merges ui_commands with config."""
        from zrb.llm.ui import SimpleUI, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        config = UIConfig(exit_commands=["/exit"])
        factory = create_ui_factory(TestSimpleUI, config=config)

        from zrb.context.shared_context import SharedContext

        ui = factory(
            ctx=SharedContext(),
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={"exit": ["/quit"]},
            initial_message="",
            initial_conversation_name="",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert ui.exit_commands == ["/quit"]

    def test_create_ui_factory_creates_ui(self):
        """Test create_ui_factory creates UI with correct configuration."""
        from zrb.llm.ui import SimpleUI, create_ui_factory

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        factory = create_ui_factory(TestSimpleUI)

        from zrb.context.shared_context import SharedContext

        ctx = SharedContext()
        ui = factory(
            ctx=ctx,
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="Test message",
            initial_conversation_name="my-session",
            initial_yolo=False,
            initial_attachments=[],
        )

        # Verify UI was created with correct settings using public properties
        assert ui.conversation_session_name == "my-session"
        assert ui.initial_message == "Test message"
        assert ui.assistant_name == "Assistant"
