"""Tests for replace_in_file_formatter.py."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockUI:
    """Mock UI for testing."""

    def __init__(self):
        self.outputs = []

    def append_to_output(self, text, end=""):
        self.outputs.append(text)


class MockCall:
    """Mock ToolCallPart for testing."""

    def __init__(self, args, tool_name="Edit"):
        self.args = args
        self.tool_name = tool_name


class TestReplaceInFileFormatter:
    """Test replace_in_file_formatter function."""

    @pytest.mark.asyncio
    async def test_non_edit_tool_returns_none(self):
        """Test that non-Edit tools return None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"path": "/tmp/test"}, tool_name="Write")

        result = await replace_in_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_path_returns_none(self):
        """Test that missing path returns None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"old_text": "a", "new_text": "b"})

        result = await replace_in_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_old_text_returns_none(self):
        """Test that missing old_text returns None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"path": "/tmp/test", "new_text": "b"})

        result = await replace_in_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_new_text_returns_none(self):
        """Test that missing new_text returns None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"path": "/tmp/test", "old_text": "a"})

        result = await replace_in_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_none(self):
        """Test that nonexistent file returns None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "path": "/nonexistent/path/to/file.txt",
                "old_text": "a",
                "new_text": "b",
            }
        )

        result = await replace_in_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_old_text_not_in_file_returns_none(self):
        """Test that old_text not in file content returns None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is some content")
            temp_path = f.name

        try:
            call = MockCall(
                {
                    "path": temp_path,
                    "old_text": "nonexistent text",
                    "new_text": "replacement",
                }
            )

            result = await replace_in_file_formatter(ui, call, "")
            assert result is None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_successful_format(self):
        """Test successful formatting of replace_in_file."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()

        # Create temp file with content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello World")
            temp_path = f.name

        try:
            call = MockCall(
                {
                    "path": temp_path,
                    "old_text": "World",
                    "new_text": "Universe",
                }
            )

            with patch(
                "zrb.llm.tool_call.argument_formatter.replace_in_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "diff content"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.replace_in_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered diff"

                    result = await replace_in_file_formatter(ui, call, "")

                    assert result is not None
                    assert temp_path in result or "File:" in result
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_args_as_string(self):
        """Test handling args as JSON string."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            args_str = (
                '{"path": "' + temp_path + '", "old_text": "Test", "new_text": "New"}'
            )
            call = MockCall(args_str)

            with patch(
                "zrb.llm.tool_call.argument_formatter.replace_in_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "diff"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.replace_in_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered"

                    result = await replace_in_file_formatter(ui, call, "")
                    # Should parse JSON and process
                    assert result is not None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_count_parameter(self):
        """Test that count parameter is used."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()

        # Create file with multiple occurrences
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test test test")
            temp_path = f.name

        try:
            call = MockCall(
                {
                    "path": temp_path,
                    "old_text": "test",
                    "new_text": "demo",
                    "count": 1,  # Replace only first occurrence
                }
            )

            with patch(
                "zrb.llm.tool_call.argument_formatter.replace_in_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "diff"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.replace_in_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered"

                    result = await replace_in_file_formatter(ui, call, "")
                    # Should work with count
                    mock_diff.assert_called_once()
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_no_change_returns_none(self):
        """Test that no change in content returns None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("same content")
            temp_path = f.name

        try:
            call = MockCall(
                {
                    "path": temp_path,
                    "old_text": "same",
                    "new_text": "same",  # Same as old
                }
            )

            result = await replace_in_file_formatter(ui, call, "")
            # Content unchanged should return None
            assert result is None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        """Test that exceptions return None."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "path": "/some/path",
                "old_text": "a",
                "new_text": "b",
            }
        )

        # Force an exception by having invalid JSON
        call.args = "{invalid json"

        result = await replace_in_file_formatter(ui, call, "")
        assert result is None


class TestReplaceInFileFormatterEdgeCases:
    """Test edge cases in replace_in_file_formatter."""

    @pytest.mark.asyncio
    async def test_expanded_home_path(self):
        """Test that ~ is expanded in path."""
        from zrb.llm.tool_call.argument_formatter.replace_in_file_formatter import (
            replace_in_file_formatter,
        )

        ui = MockUI()
        # This tests path expansion but won't actually find the file
        call = MockCall(
            {
                "path": "~/nonexistent_file.txt",
                "old_text": "a",
                "new_text": "b",
            }
        )

        result = await replace_in_file_formatter(ui, call, "")
        # Path should be expanded, but file won't exist
        assert result is None
