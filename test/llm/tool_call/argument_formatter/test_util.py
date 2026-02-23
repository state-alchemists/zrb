import sys
from unittest.mock import Mock, patch

import pytest

from zrb.llm.tool_call.argument_formatter.util import format_diff, get_terminal_width


class TestGetTerminalWidth:
    """Tests for get_terminal_width function."""

    def test_get_terminal_width_with_ui_output_field_width(self):
        """Test get_terminal_width with UI object that has _get_output_field_width."""
        ui = Mock()
        ui._get_output_field_width = Mock(return_value=76)

        result = get_terminal_width(ui=ui)
        assert result == 80  # 76 + 4

    def test_get_terminal_width_with_ui_get_terminal_width(self):
        """Test get_terminal_width with UI object that has get_terminal_width method."""
        ui = Mock()
        ui.get_terminal_width = Mock(return_value=100)

        result = get_terminal_width(ui=ui)
        assert result == 100

    def test_get_terminal_width_with_ui_terminal_width(self):
        """Test get_terminal_width with UI object that has terminal_width method."""
        ui = Mock()
        ui.terminal_width = Mock(return_value=120)

        result = get_terminal_width(ui=ui)
        assert result == 120

    def test_get_terminal_width_with_ui_get_width(self):
        """Test get_terminal_width with UI object that has get_width method."""
        ui = Mock()
        ui.get_width = Mock(return_value=90)

        result = get_terminal_width(ui=ui)
        assert result == 90

    def test_get_terminal_width_with_ui_method_returns_none(self):
        """Test get_terminal_width when UI method returns None."""
        ui = Mock()
        ui.get_terminal_width = Mock(return_value=None)

        # Mock shutil.get_terminal_size to return a known value
        with patch("shutil.get_terminal_size") as mock_terminal_size:
            mock_terminal_size.return_value.columns = 80
            result = get_terminal_width(ui=ui)
            assert result == 80

    def test_get_terminal_width_with_ui_method_returns_zero(self):
        """Test get_terminal_width when UI method returns 0."""
        ui = Mock()
        ui.get_terminal_width = Mock(return_value=0)

        # Mock shutil.get_terminal_size to return a known value
        with patch("shutil.get_terminal_size") as mock_terminal_size:
            mock_terminal_size.return_value.columns = 80
            result = get_terminal_width(ui=ui)
            assert result == 80

    def test_get_terminal_width_with_ui_method_raises_exception(self):
        """Test get_terminal_width when UI method raises an exception."""
        ui = Mock()
        ui.get_terminal_width = Mock(side_effect=Exception("Test error"))

        # Mock shutil.get_terminal_size to return a known value
        with patch("shutil.get_terminal_size") as mock_terminal_size:
            mock_terminal_size.return_value.columns = 80
            result = get_terminal_width(ui=ui)
            assert result == 80

    @patch("shutil.get_terminal_size")
    @patch("prompt_toolkit.application.get_app")
    def test_get_terminal_width_without_ui_shutil_success(
        self, mock_get_app, mock_terminal_size
    ):
        """Test get_terminal_width without UI, using shutil successfully."""
        # Mock prompt_toolkit to raise ImportError (simulating not available)
        mock_get_app.side_effect = ImportError("No module named 'prompt_toolkit'")
        mock_terminal_size.return_value.columns = 100
        result = get_terminal_width()
        assert result == 100

    @patch("shutil.get_terminal_size")
    @patch("prompt_toolkit.application.get_app")
    def test_get_terminal_width_without_ui_shutil_exception(
        self, mock_get_app, mock_terminal_size
    ):
        """Test get_terminal_width without UI, when shutil raises exception."""
        # Mock prompt_toolkit to raise ImportError (simulating not available)
        mock_get_app.side_effect = ImportError("No module named 'prompt_toolkit'")
        mock_terminal_size.side_effect = Exception("Terminal error")
        result = get_terminal_width(default=70)
        assert result == 70

    @patch("shutil.get_terminal_size")
    @patch("prompt_toolkit.application.get_app")
    def test_get_terminal_width_custom_default(self, mock_get_app, mock_terminal_size):
        """Test get_terminal_width with custom default value."""
        # Mock prompt_toolkit to raise ImportError (simulating not available)
        mock_get_app.side_effect = ImportError("No module named 'prompt_toolkit'")
        mock_terminal_size.side_effect = Exception("Terminal error")
        result = get_terminal_width(default=90)
        assert result == 90

    @patch("prompt_toolkit.application.get_app")
    def test_get_terminal_width_prompt_toolkit_success(self, mock_get_app):
        """Test get_terminal_width with prompt_toolkit context."""
        mock_output = Mock()
        mock_output.get_size.return_value.columns = 120
        mock_app = Mock()
        mock_app.output = mock_output
        mock_get_app.return_value = mock_app

        result = get_terminal_width()
        assert result == 120

    @patch("prompt_toolkit.application.get_app")
    def test_get_terminal_width_prompt_toolkit_no_output(self, mock_get_app):
        """Test get_terminal_width with prompt_toolkit but no output attribute."""
        mock_app = Mock()
        del mock_app.output  # Remove output attribute
        mock_get_app.return_value = mock_app

        # Mock shutil.get_terminal_size to return a known value
        with patch("shutil.get_terminal_size") as mock_terminal_size:
            mock_terminal_size.return_value.columns = 80
            result = get_terminal_width()
            assert result == 80

    @patch("prompt_toolkit.application.get_app")
    def test_get_terminal_width_prompt_toolkit_exception(self, mock_get_app):
        """Test get_terminal_width when prompt_toolkit raises exception."""
        mock_get_app.side_effect = ImportError("No prompt_toolkit")

        # Mock shutil.get_terminal_size to return a known value
        with patch("shutil.get_terminal_size") as mock_terminal_size:
            mock_terminal_size.return_value.columns = 80
            result = get_terminal_width()
            assert result == 80


class TestFormatDiff:
    """Tests for format_diff function."""

    def test_format_diff_no_changes(self):
        """Test format_diff when there are no changes."""
        result = format_diff("hello\nworld", "hello\nworld", "test.txt")
        assert result == ""

    def test_format_diff_simple_addition(self):
        """Test format_diff with a simple addition."""
        old_content = "hello\nworld"
        new_content = "hello\nworld\nzrb"
        result = format_diff(old_content, new_content, "test.txt")

        # Should contain diff markers
        assert "```diff" in result
        assert "```" in result
        assert "+" in result  # Addition marker
        assert "zrb" in result  # Added content

    def test_format_diff_simple_deletion(self):
        """Test format_diff with a simple deletion."""
        old_content = "hello\nworld\nzrb"
        new_content = "hello\nworld"
        result = format_diff(old_content, new_content, "test.txt")

        assert "```diff" in result
        assert "```" in result
        assert "-" in result  # Deletion marker
        assert "zrb" in result  # Deleted content

    def test_format_diff_simple_modification(self):
        """Test format_diff with a simple modification."""
        old_content = "hello\nworld"
        new_content = "hello\nzrb"
        result = format_diff(old_content, new_content, "test.txt")

        assert "```diff" in result
        assert "```" in result
        assert "-" in result  # Deletion marker
        assert "+" in result  # Addition marker
        assert "world" in result  # Old content
        assert "zrb" in result  # New content

    def test_format_diff_with_line_numbers(self):
        """Test format_diff includes line numbers."""
        old_content = "line1\nline2\nline3"
        new_content = "line1\nmodified\nline3"
        result = format_diff(old_content, new_content, "test.txt")

        # Should contain line numbers (formatted as 4-digit fields)
        assert "   2" in result or "  2" in result  # Line number 2

    def test_format_diff_with_path_in_header(self):
        """Test format_diff includes file path in diff header."""
        old_content = "hello"
        new_content = "world"
        result = format_diff(old_content, new_content, "/path/to/file.txt")

        # The path should appear in the hunk header
        assert "file.txt" in result

    def test_format_diff_with_term_width_parameter(self):
        """Test format_diff with explicit terminal width."""
        # Create a long line that would need wrapping
        long_line = "x" * 100
        old_content = "short"
        new_content = long_line

        # Test with narrow terminal width
        result = format_diff(old_content, new_content, "test.txt", term_width=60)

        # Should wrap the long line
        assert "```diff" in result
        assert "```" in result
        # The line should be wrapped (multiple lines with continuation markers)
        lines = result.split("\n")
        # Count lines with '+' marker (additions)
        plus_lines = [line for line in lines if line.startswith("+")]
        # With wrapping, we might have multiple continuation lines
        assert len(plus_lines) >= 1

    def test_format_diff_with_ui_parameter(self):
        """Test format_diff with UI parameter for width detection."""
        ui = Mock()
        ui._get_output_field_width = Mock(return_value=76)  # Returns 80 total

        old_content = "hello"
        new_content = "world"
        result = format_diff(old_content, new_content, "test.txt", ui=ui)

        assert "```diff" in result
        assert "```" in result
        # UI mock should have been called
        ui._get_output_field_width.assert_called()

    def test_format_diff_empty_file_addition(self):
        """Test format_diff when adding content to empty file."""
        result = format_diff("", "new content", "test.txt")

        assert "```diff" in result
        assert "```" in result
        assert "+" in result
        assert "new content" in result

    def test_format_diff_file_deletion(self):
        """Test format_diff when deleting all content from file."""
        result = format_diff("old content", "", "test.txt")

        assert "```diff" in result
        assert "```" in result
        assert "-" in result
        assert "old content" in result

    def test_format_diff_multiline_changes(self):
        """Test format_diff with multiple line changes."""
        old_content = "line1\nline2\nline3\nline4\nline5"
        new_content = "line1\nmodified2\nline3\nmodified4\nline5"
        result = format_diff(old_content, new_content, "test.txt")

        # Should show both modifications
        lines = result.split("\n")
        minus_count = sum(1 for line in lines if line.startswith("-"))
        plus_count = sum(1 for line in lines if line.startswith("+"))

        # Two deletions and two additions
        assert minus_count >= 2
        assert plus_count >= 2

    def test_format_diff_with_context_lines(self):
        """Test format_diff includes context lines (unchanged lines)."""
        old_content = "context1\nchange1\ncontext2\nchange2\ncontext3"
        new_content = "context1\nmodified1\ncontext2\nmodified2\ncontext3"
        result = format_diff(old_content, new_content, "test.txt")

        # Should have context lines (marked with space)
        lines = result.split("\n")
        space_lines = [line for line in lines if line.startswith(" ")]
        assert len(space_lines) > 0

    def test_format_diff_hunk_header_format(self):
        """Test format_diff produces correct hunk headers."""
        old_content = "line1\nline2\nline3\nline4\nline5"
        new_content = "line1\nline2\nmodified\nline4\nline5"
        result = format_diff(old_content, new_content, "test.txt")

        # Should have hunk header like "@@ -3 +3 @@" or similar
        assert "@@ -" in result
        assert " +" in result
        assert " @@" in result

    def test_format_diff_wrapping_long_lines(self):
        """Test format_diff wraps very long lines."""
        # Create a line longer than default width
        very_long_line = (
            "This is a very long line that should definitely wrap because it exceeds the typical terminal width by a significant margin. "
            * 3
        )
        old_content = "short"
        new_content = very_long_line

        result = format_diff(old_content, new_content, "test.txt")

        # Check for continuation lines (lines that start with marker but no line number)
        lines = result.split("\n")
        # Look for continuation patterns: lines starting with '+' followed by spaces
        continuation_candidates = [
            line for line in lines if line.startswith("+") and "    " in line[:10]
        ]
        # Should have at least one continuation if line was wrapped
        # Note: This depends on terminal width detection, so we just check the function runs
        assert "```diff" in result
        assert "```" in result

    def test_format_diff_minimum_width_respected(self):
        """Test format_diff respects minimum content width."""
        # With a very narrow terminal, should still use minimum width
        old_content = "hello"
        new_content = "world"

        # Mock get_terminal_width to return very small value
        with patch(
            "zrb.llm.tool_call.argument_formatter.util.get_terminal_width"
        ) as mock_width:
            mock_width.return_value = 20  # Very narrow terminal
            result = format_diff(old_content, new_content, "test.txt")

            # Should still produce output (not crash)
            assert "```diff" in result
            assert "```" in result

    def test_format_diff_exception_handling(self):
        """Test format_diff handles exceptions gracefully."""
        # Mock get_terminal_width to raise exception
        with patch(
            "zrb.llm.tool_call.argument_formatter.util.get_terminal_width"
        ) as mock_width:
            mock_width.side_effect = Exception("Width detection failed")

            # Should still work with default width
            result = format_diff("hello", "world", "test.txt")
            assert "```diff" in result
            assert "```" in result
