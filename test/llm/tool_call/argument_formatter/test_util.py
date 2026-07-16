import sys
from unittest.mock import Mock, patch

import pytest

from zrb.llm.tool_call.argument_formatter.util import format_diff


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

    def test_format_diff_auto_detects_wide_terminal(self):
        """Auto width detection must use the stdin-aware get_terminal_size.

        Regression: the TUI redirects stdout/stderr fds to a capture pipe, so
        shutil.get_terminal_size() (stdout-only) falls back to 80 and long diff
        lines wrap at ~62. The robust helper recovers the real width. Patching
        it here proves format_diff reads that width (no-op if it were shutil).
        """
        long_line = "x" * 160
        wide = Mock()
        wide.columns = 200
        with patch(
            "zrb.llm.tool_call.argument_formatter.util.get_terminal_size",
            return_value=wide,
        ):
            result = format_diff("short", long_line, "test.txt")

        # The 160-char line fits within 200 cols, so it is NOT wrapped down to
        # the ~62-col (80 - prefix) width the old shutil fallback produced.
        widest = max(len(line) for line in result.split("\n"))
        assert widest > 100

    def test_format_diff_with_ui_parameter(self):
        """Test format_diff with UI parameter for width detection."""
        ui = Mock()
        ui.output_field_width = 76

        old_content = "hello"
        new_content = "world"
        result = format_diff(old_content, new_content, "test.txt", ui=ui)

        assert "```diff" in result
        assert "```" in result

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
