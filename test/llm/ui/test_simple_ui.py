"""Tests for simple_ui.py."""

import pytest

from zrb.llm.ui.simple_ui import UIConfig


class TestUIConfig:
    def test_default_config(self):
        config = UIConfig.default()
        assert config.assistant_name == "Assistant"
        assert isinstance(config.exit_commands, list)
        assert isinstance(config.info_commands, list)
        assert config.is_yolo is False

    def test_minimal_config(self):
        config = UIConfig.minimal()
        assert config.exit_commands == ["/exit"]
        assert config.info_commands == []
        assert config.save_commands == []

    def test_custom_config(self):
        config = UIConfig(
            assistant_name="CustomBot",
            exit_commands=["/quit", "/q"],
            is_yolo=True,
        )
        assert config.assistant_name == "CustomBot"
        assert config.exit_commands == ["/quit", "/q"]
        assert config.is_yolo is True

    def test_merge_commands_with_exit(self):
        config = UIConfig.default()
        result = config.merge_commands({"exit": ["/quit"]})
        assert result.exit_commands == ["/quit"]
        assert result.info_commands == config.info_commands

    def test_merge_commands_with_info(self):
        config = UIConfig.default()
        result = config.merge_commands({"info": ["/h"]})
        assert result.info_commands == ["/h"]
        assert result.exit_commands == config.exit_commands

    def test_merge_commands_with_save(self):
        config = UIConfig.default()
        result = config.merge_commands({"save": ["/s"]})
        assert result.save_commands == ["/s"]

    def test_merge_commands_with_load(self):
        config = UIConfig.default()
        result = config.merge_commands({"load": ["/l"]})
        assert result.load_commands == ["/l"]

    def test_merge_commands_with_attach(self):
        config = UIConfig.default()
        result = config.merge_commands({"attach": ["/a"]})
        assert result.attach_commands == ["/a"]

    def test_merge_commands_with_redirect(self):
        config = UIConfig.default()
        result = config.merge_commands({"redirect": ["/r"]})
        assert result.redirect_output_commands == ["/r"]

    def test_merge_commands_with_yolo(self):
        config = UIConfig.default()
        result = config.merge_commands({"yolo_toggle": ["/y"]})
        assert result.yolo_toggle_commands == ["/y"]

    def test_merge_commands_with_model(self):
        config = UIConfig.default()
        result = config.merge_commands({"set_model": ["/m"]})
        assert result.set_model_commands == ["/m"]

    def test_merge_commands_with_exec(self):
        config = UIConfig.default()
        result = config.merge_commands({"exec": ["/e"]})
        assert result.exec_commands == ["/e"]

    def test_merge_commands_preserves_other(self):
        config = UIConfig(
            assistant_name="Bot",
            is_yolo=True,
        )
        result = config.merge_commands({"exit": ["/quit"]})
        assert result.exit_commands == ["/quit"]
        assert result.assistant_name == "Bot"
        assert result.is_yolo is True

    def test_yolo_xcom_key_default(self):
        config = UIConfig.default()
        assert config.yolo_xcom_key == ""

    def test_conversation_session_name_default(self):
        config = UIConfig.default()
        assert config.conversation_session_name == ""

    def test_custom_yolo_xcom_key(self):
        config = UIConfig(yolo_xcom_key="my-key")
        assert config.yolo_xcom_key == "my-key"

    def test_custom_conversation_session_name(self):
        config = UIConfig(conversation_session_name="my-session")
        assert config.conversation_session_name == "my-session"

    def test_empty_commands_lists(self):
        config = UIConfig(
            exit_commands=[],
            info_commands=[],
            save_commands=[],
            load_commands=[],
        )
        assert config.exit_commands == []
        assert config.info_commands == []
        assert config.save_commands == []
        assert config.load_commands == []
