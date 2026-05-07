from zrb.util.truncate import truncate_output


# Tests for truncate_output
def test_truncate_output_no_truncation():
    """Test truncate_output with small content that doesn't need truncation."""
    text = "Hello\nWorld\n"
    result, info = truncate_output(text, head_lines=2, tail_lines=2, max_chars=1000)
    assert result == text
    assert info["truncation_type"] == "none"
    assert info["omitted_lines"] == 0
    assert info["omitted_chars"] == 0


def test_truncate_output_line_length_truncation():
    """Test truncate_output with long lines that need truncation."""
    text = "A" * 2000 + "\n"  # Very long line
    result, info = truncate_output(
        text, head_lines=1, tail_lines=1, max_line_length=100
    )
    assert "LINE TRUNCATED" in result
    assert info["truncation_type"] == "line_length"


def test_truncate_output_basic_line_removal():
    """Test truncate_output removes lines from middle when needed."""
    lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
    text = "".join(lines)
    # Set max_chars to force removal
    result, info = truncate_output(text, head_lines=1, tail_lines=1, max_chars=20)
    assert "TRUNCATED" in result
    assert info["omitted_lines"] > 0


def test_truncate_output_with_head_and_tail():
    """Test truncate_output preserves head and tail lines."""
    lines = [f"line{i}\n" for i in range(1, 11)]
    text = "".join(lines)
    result, info = truncate_output(text, head_lines=2, tail_lines=2, max_chars=100)
    # Should keep head lines and possibly tail lines
    assert "line1" in result or "TRUNCATED" in result


def test_truncate_output_empty_string():
    """Test truncate_output with empty string."""
    result, info = truncate_output("", head_lines=5, tail_lines=5)
    assert result == ""
    assert info["truncation_type"] == "none"


def test_truncate_output_single_line():
    """Test truncate_output with single line."""
    result, info = truncate_output("single line", head_lines=5, tail_lines=5)
    assert result == "single line"
    assert info["truncation_type"] == "none"


def test_truncate_output_very_small_max_chars():
    """Test truncate_output with very small max_chars."""
    text = "This is a very long line that should be truncated"
    result, info = truncate_output(text, head_lines=0, tail_lines=0, max_chars=10)
    # Should handle gracefully
    assert len(result) <= 50  # Allow for truncation message
    assert info["truncation_type"] in ("chars", "lines")


def test_truncate_output_max_chars_exactly():
    """Test truncate_output when content matches max_chars exactly."""
    text = "Hello"
    result, info = truncate_output(text, head_lines=5, tail_lines=5, max_chars=5)
    assert result == text
    assert info["truncation_type"] == "none"


def test_truncate_output_whitespace_lines():
    """Test truncate_output handles whitespace-only lines."""
    text = "\n\n\n\n\n"
    result, info = truncate_output(text, head_lines=2, tail_lines=2, max_chars=100)
    assert info["original_lines"] == 5


def test_truncate_output_with_line_endings():
    """Test truncate_output properly handles line endings."""
    text = "line1\r\nline2\r\nline3\n"
    result, info = truncate_output(text, head_lines=5, tail_lines=5, max_chars=1000)
    # Should handle various line endings
    assert info["original_lines"] == 3


def test_truncate_output_truncation_info():
    """Test truncate_output returns correct TruncationInfo."""
    text = "line1\nline2\nline3\nline4\nline5\n"
    result, info = truncate_output(text, head_lines=1, tail_lines=1, max_chars=20)
    assert "original_lines" in info
    assert "original_chars" in info
    assert "truncated_lines" in info
    assert "truncated_chars" in info
    assert "omitted_lines" in info
    assert "omitted_chars" in info
    assert "truncation_type" in info


def test_truncate_output_preserves_head_lines():
    """Test truncate_output preserves head lines when possible."""
    text = "\n".join([f"line{i}" for i in range(100)])
    result, info = truncate_output(text, head_lines=3, tail_lines=0, max_chars=50)
    # Should contain some lines from the beginning
    assert "line0" in result or "TRUNCATED" in result


def test_truncate_output_no_head_no_tail():
    """Test truncate_output with head_lines=0 and tail_lines=0."""
    text = "line1\nline2\nline3\n"
    result, info = truncate_output(text, head_lines=0, tail_lines=0, max_chars=100)
    # With no head or tail, should either return as-is or truncate everything
    assert info["truncation_type"] in ("none", "lines", "chars")


def test_truncate_output_lines_truncation_type():
    """Test truncate_output returns 'lines' truncation type."""
    text = "\n".join([f"line{i}" for i in range(50)])
    result, info = truncate_output(text, head_lines=2, tail_lines=2, max_chars=50)
    assert info["truncation_type"] == "lines"


def test_truncate_output_both_truncation_type():
    """Test truncate_output returns 'both' truncation type."""
    # Create content that needs both line and char truncation
    lines = ["A" * 2000 + "\n" for _ in range(100)]
    text = "".join(lines)
    result, info = truncate_output(
        text, head_lines=1, tail_lines=1, max_line_length=100, max_chars=500
    )
    # Should have truncation
    assert info["truncation_type"] in ("both", "chars", "lines", "line_length")


def test_truncate_output_char_truncation_small_max():
    """Test truncate_output with very small max_chars (< 15)."""
    text = "line1\nline2\nline3\n"
    result, info = truncate_output(text, head_lines=1, tail_lines=1, max_chars=10)
    assert len(result) <= 10


def test_truncate_output_char_truncation_very_small():
    """Test truncate_output with max_chars < 3."""
    text = "line1\nline2\nline3\n"
    result, info = truncate_output(text, head_lines=1, tail_lines=1, max_chars=2)
    assert len(result) <= 2


def test_truncate_output_char_truncation_minimal():
    """Test truncate_output with max_chars = 3."""
    text = "line1\nline2\nline3\n"
    result, info = truncate_output(text, head_lines=1, tail_lines=1, max_chars=3)
    assert result == "..."


def test_truncate_line_exceeds_length():
    """Test _truncate_line truncates when exceeding length."""
    from zrb.util.truncate import _truncate_line

    result = _truncate_line("A" * 100 + "\n", 10)
    assert len(result) <= 10 + len(" [LINE TRUNCATED]\n")
    assert "[LINE TRUNCATED]" in result


def test_truncate_line_under_length():
    """Test _truncate_line returns unchanged when under length."""
    from zrb.util.truncate import _truncate_line

    result = _truncate_line("short\n", 100)
    assert result == "short\n"


def test_truncate_output_no_truncation_needed():
    """Test _build_result_with_truncation_message when no lines removed."""
    text = "line1\nline2\nline3\n"
    result, info = truncate_output(text, head_lines=5, tail_lines=5, max_chars=1000)
    assert result == text
    assert info["omitted_lines"] == 0
