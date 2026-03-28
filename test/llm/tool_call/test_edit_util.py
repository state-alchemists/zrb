"""Tests for edit_util.py - Content editing via text editor."""

import os
from unittest.mock import MagicMock, patch

import pytest


class MockUI:
    """Mock UI for testing."""

    def __init__(self):
        self.commands = []

    async def run_interactive_command(self, cmd, shell=False):
        self.commands.append((cmd, shell))


class TestEditContentViaEditor:
    """Tests for edit_content_via_editor function."""

    @pytest.mark.asyncio
    async def test_editor_uses_custom_text_editor(self):
        """Test that custom text_editor is used instead of CFG.EDITOR."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MockUI()
        content = {"key": "value"}

        with patch(
            "zrb.llm.tool_call.edit_util.yaml_dump", return_value="key: value\n"
        ):
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_tf = MagicMock()
                mock_tf.name = "/tmp/test.yaml"
                mock_tf.write = MagicMock()
                mock_tf.__enter__ = MagicMock(return_value=mock_tf)
                mock_tf.__exit__ = MagicMock(return_value=None)
                mock_temp.return_value = mock_tf

                with patch("builtins.open", create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_file.__enter__ = MagicMock(return_value=mock_file)
                    mock_file.__exit__ = MagicMock(return_value=None)
                    mock_file.read.return_value = "key: modified\n"
                    mock_open.return_value = mock_file

                    with patch("os.remove"):
                        with patch("yaml.safe_load", return_value={"key": "modified"}):
                            await edit_content_via_editor(
                                ui, content, text_editor="myeditor"
                            )
                            # Should use custom editor
                            assert ui.commands[0][0] == ["myeditor", "/tmp/test.yaml"]

    @pytest.mark.asyncio
    async def test_returns_original_content_when_unchanged(self):
        """Test that original content is returned when file is unchanged."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MockUI()
        content = {"key": "value"}
        original_yaml = "key: value\n"

        with patch("zrb.llm.tool_call.edit_util.yaml_dump", return_value=original_yaml):
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_tf = MagicMock()
                mock_tf.name = "/tmp/test.yaml"
                mock_tf.write = MagicMock()
                mock_tf.__enter__ = MagicMock(return_value=mock_tf)
                mock_tf.__exit__ = MagicMock(return_value=None)
                mock_temp.return_value = mock_tf

                with patch("builtins.open", create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_file.__enter__ = MagicMock(return_value=mock_file)
                    mock_file.__exit__ = MagicMock(return_value=None)
                    mock_file.read.return_value = original_yaml  # Same content
                    mock_open.return_value = mock_file

                    with patch("os.remove"):
                        result = await edit_content_via_editor(
                            ui, content, text_editor="vim"
                        )
                        # When content unchanged, should return original
                        assert result == content

    @pytest.mark.asyncio
    async def test_returns_none_on_parse_error(self):
        """Test that None is returned when content cannot be parsed."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MockUI()
        content = {"key": "value"}

        with patch(
            "zrb.llm.tool_call.edit_util.yaml_dump", return_value="key: value\n"
        ):
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_tf = MagicMock()
                mock_tf.name = "/tmp/test.yaml"
                mock_tf.write = MagicMock()
                mock_tf.__enter__ = MagicMock(return_value=mock_tf)
                mock_tf.__exit__ = MagicMock(return_value=None)
                mock_temp.return_value = mock_tf

                with patch("builtins.open", create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_file.__enter__ = MagicMock(return_value=mock_file)
                    mock_file.__exit__ = MagicMock(return_value=None)
                    mock_file.read.return_value = "invalid: yaml: [unclosed"
                    mock_open.return_value = mock_file

                    with patch("os.remove"):
                        result = await edit_content_via_editor(
                            ui, content, text_editor="vim"
                        )
                        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_non_dict_result(self):
        """Test that None is returned when edited content is not a dict."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MockUI()
        content = {"key": "value"}

        with patch(
            "zrb.llm.tool_call.edit_util.yaml_dump", return_value="key: value\n"
        ):
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_tf = MagicMock()
                mock_tf.name = "/tmp/test.yaml"
                mock_tf.write = MagicMock()
                mock_tf.__enter__ = MagicMock(return_value=mock_tf)
                mock_tf.__exit__ = MagicMock(return_value=None)
                mock_temp.return_value = mock_tf

                with patch("builtins.open", create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_file.__enter__ = MagicMock(return_value=mock_file)
                    mock_file.__exit__ = MagicMock(return_value=None)
                    mock_file.read.return_value = (
                        "- item1\n- item2\n"  # A list, not dict
                    )
                    mock_open.return_value = mock_file

                    with patch("os.remove"):
                        with patch("yaml.safe_load", return_value=["item1", "item2"]):
                            result = await edit_content_via_editor(
                                ui, content, text_editor="vim"
                            )
                            # list is not dict, should return None
                            assert result is None

    @pytest.mark.asyncio
    async def test_json_fallback_on_yaml_dump_error(self):
        """Test that editor falls back to JSON when YAML dump fails."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MockUI()
        content = {"key": "value"}

        with patch(
            "zrb.llm.tool_call.edit_util.yaml_dump", side_effect=Exception("YAML error")
        ):
            with patch("json.dumps", return_value='{"key": "value"}'):
                with patch("tempfile.NamedTemporaryFile") as mock_temp:
                    mock_tf = MagicMock()
                    mock_tf.name = "/tmp/test.json"  # Note: JSON extension
                    mock_tf.write = MagicMock()
                    mock_tf.__enter__ = MagicMock(return_value=mock_tf)
                    mock_tf.__exit__ = MagicMock(return_value=None)
                    mock_temp.return_value = mock_tf

                    with patch("builtins.open", create=True) as mock_open:
                        mock_file = MagicMock()
                        mock_file.__enter__ = MagicMock(return_value=mock_file)
                        mock_file.__exit__ = MagicMock(return_value=None)
                        mock_file.read.return_value = '{"key": "modified"}'
                        mock_open.return_value = mock_file

                        with patch("os.remove"):
                            with patch("json.loads", return_value={"key": "modified"}):
                                result = await edit_content_via_editor(
                                    ui, content, text_editor="vim"
                                )
                                assert result == {"key": "modified"}

    @pytest.mark.asyncio
    async def test_uses_cfg_editor_when_no_custom_editor(self):
        """Test that CFG.EDITOR is used when text_editor is not provided."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MockUI()
        content = {"key": "value"}

        with patch("zrb.llm.tool_call.edit_util.CFG") as mock_cfg:
            mock_cfg.EDITOR = "nano"
            with patch(
                "zrb.llm.tool_call.edit_util.yaml_dump", return_value="key: value\n"
            ):
                with patch("tempfile.NamedTemporaryFile") as mock_temp:
                    mock_tf = MagicMock()
                    mock_tf.name = "/tmp/test.yaml"
                    mock_tf.write = MagicMock()
                    mock_tf.__enter__ = MagicMock(return_value=mock_tf)
                    mock_tf.__exit__ = MagicMock(return_value=None)
                    mock_temp.return_value = mock_tf

                    with patch("builtins.open", create=True) as mock_open:
                        mock_file = MagicMock()
                        mock_file.__enter__ = MagicMock(return_value=mock_file)
                        mock_file.__exit__ = MagicMock(return_value=None)
                        mock_file.read.return_value = "key: modified\n"
                        mock_open.return_value = mock_file

                        with patch("os.remove"):
                            with patch(
                                "yaml.safe_load", return_value={"key": "modified"}
                            ):
                                await edit_content_via_editor(ui, content)
                                # Should use nano from CFG.EDITOR
                                assert ui.commands[0][0] == ["nano", "/tmp/test.yaml"]
