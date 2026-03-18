"""Tests for write_file_formatter.py."""

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

    def __init__(self, args, tool_name="Write"):
        self.args = args
        self.tool_name = tool_name


class TestWriteFileFormatter:
    """Test write_file_formatter function."""

    @pytest.mark.asyncio
    async def test_non_write_tool_returns_none(self):
        """Test that non-Write tools return None."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"path": "/tmp/test"}, tool_name="Read")

        result = await write_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_path_returns_none(self):
        """Test that missing path returns None."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"content": "test content"})

        result = await write_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_content_returns_none(self):
        """Test that missing content returns None."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()
        call = MockCall({"path": "/tmp/test.txt"})

        result = await write_file_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_new_file(self):
        """Test formatting for a new file."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "path": "/tmp/newfile.txt",
                "content": "Hello World",
            }
        )

        with patch(
            "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
        ) as mock_diff:
            mock_diff.return_value = "created diff"

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
            ) as mock_render:
                mock_render.return_value = "rendered"

                result = await write_file_formatter(ui, call, "")

                assert result is not None
                assert "newfile.txt" in result or "File:" in result

    @pytest.mark.asyncio
    async def test_successful_existing_file(self):
        """Test formatting for overwriting an existing file."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("old content")
            temp_path = f.name

        try:
            call = MockCall(
                {
                    "path": temp_path,
                    "content": "new content",
                }
            )

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "diff content"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered diff"

                    result = await write_file_formatter(ui, call, "")

                    assert result is not None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_append_mode(self):
        """Test formatting with append mode."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("existing")
            temp_path = f.name

        try:
            call = MockCall(
                {
                    "path": temp_path,
                    "content": " appended",
                    "mode": "a",
                }
            )

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "append diff"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered"

                    result = await write_file_formatter(ui, call, "")
                    assert result is not None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_args_as_string(self):
        """Test handling args as JSON string."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_file_formatter,
        )

        ui = MockUI()
        args_str = '{"path": "/tmp/test.txt", "content": "test"}'
        call = MockCall(args_str)

        with patch(
            "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
        ) as mock_diff:
            mock_diff.return_value = "diff"

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
            ) as mock_render:
                mock_render.return_value = "rendered"

                result = await write_file_formatter(ui, call, "")
                assert result is not None


class TestWriteFilesFormatter:
    """Test write_files_formatter function."""

    @pytest.mark.asyncio
    async def test_non_writemany_tool_returns_none(self):
        """Test that non-WriteMany tools return None."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall({"files": []}, tool_name="Write")

        result = await write_files_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_files_returns_none(self):
        """Test that empty files list returns None."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall({"files": []}, tool_name="WriteMany")

        result = await write_files_formatter(ui, call, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_single_file_write(self):
        """Test writing multiple files."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "files": [
                    {"path": "/tmp/file1.txt", "content": "content1"},
                ]
            },
            tool_name="WriteMany",
        )

        with patch(
            "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
        ) as mock_diff:
            mock_diff.return_value = "diff1"

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
            ) as mock_render:
                mock_render.return_value = "rendered1"

                result = await write_files_formatter(ui, call, "")
                assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_files_write(self):
        """Test writing multiple files."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "files": [
                    {"path": "/tmp/file1.txt", "content": "content1"},
                    {"path": "/tmp/file2.txt", "content": "content2"},
                ]
            },
            tool_name="WriteMany",
        )

        with patch(
            "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
        ) as mock_diff:
            mock_diff.return_value = "diff"

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
            ) as mock_render:
                mock_render.return_value = "rendered"

                result = await write_files_formatter(ui, call, "")
                assert result is not None
                # Should contain both files

    @pytest.mark.asyncio
    async def test_missing_path_in_file_entry(self):
        """Test handling missing path in file entry."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "files": [
                    {"content": "content without path"},  # Missing path
                ]
            },
            tool_name="WriteMany",
        )

        result = await write_files_formatter(ui, call, "")
        # Should skip the entry with missing path
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_content_in_file_entry(self):
        """Test handling missing content in file entry."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall(
            {
                "files": [
                    {"path": "/tmp/test.txt"},  # Missing content
                ]
            },
            tool_name="WriteMany",
        )

        result = await write_files_formatter(ui, call, "")
        # Should skip the entry with missing content
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        """Test that exceptions return None."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            write_files_formatter,
        )

        ui = MockUI()
        call = MockCall("{invalid json", tool_name="WriteMany")

        result = await write_files_formatter(ui, call, "")
        assert result is None


class TestFormatSingleWrite:
    """Test _format_single_write helper function."""

    def test_new_file_format(self):
        """Test formatting for new file."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            _format_single_write,
        )

        ui = MockUI()

        with patch(
            "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
        ) as mock_diff:
            mock_diff.return_value = "new file diff"

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
            ) as mock_render:
                mock_render.return_value = "rendered"

                result = _format_single_write(
                    "/nonexistent/path/file.txt", "content", "w", ui
                )
                assert result is not None
                assert "New File" in result or "new" in result.lower()

    def test_overwrite_format(self):
        """Test formatting for overwrite."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            _format_single_write,
        )

        ui = MockUI()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("old")
            temp_path = f.name

        try:
            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "overwrite diff"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered"

                    result = _format_single_write(temp_path, "new content", "w", ui)
                    assert result is not None
        finally:
            os.unlink(temp_path)

    def test_append_format(self):
        """Test formatting for append."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            _format_single_write,
        )

        ui = MockUI()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("existing")
            temp_path = f.name

        try:
            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = "append diff"

                with patch(
                    "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
                ) as mock_render:
                    mock_render.return_value = "rendered"

                    result = _format_single_write(temp_path, " appended", "a", ui)
                    assert result is not None
                    assert "Append" in result
        finally:
            os.unlink(temp_path)

    def test_no_changes_format(self):
        """Test formatting when no changes."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            _format_single_write,
        )

        ui = MockUI()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("same content")
            temp_path = f.name

        try:
            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
            ) as mock_diff:
                mock_diff.return_value = None  # No changes

                result = _format_single_write(temp_path, "same content", "w", ui)
                assert "No changes" in result
        finally:
            os.unlink(temp_path)

    def test_expand_home_path(self):
        """Test that ~ is expanded in path."""
        from zrb.llm.tool_call.argument_formatter.write_file_formatter import (
            _format_single_write,
        )

        ui = MockUI()

        with patch(
            "zrb.llm.tool_call.argument_formatter.write_file_formatter.format_diff"
        ) as mock_diff:
            mock_diff.return_value = "diff"

            with patch(
                "zrb.llm.tool_call.argument_formatter.write_file_formatter.render_markdown"
            ) as mock_render:
                mock_render.return_value = "rendered"

                # Path with ~ will be expanded
                result = _format_single_write("~/some_file.txt", "content", "w", ui)
                # Should work (file won't exist)
                assert result is not None
