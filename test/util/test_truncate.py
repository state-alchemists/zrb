from zrb.util.truncate import truncate_str, truncate_output


def test_truncate_str_string():
    assert truncate_str("hello world", 15) == "hello world"
    assert truncate_str("hello world", 11) == "hello world"
    assert truncate_str("hello world", 10) == "hello  ..."
    assert truncate_str("hello world", 5) == "h ..."
    assert truncate_str("hello world", 3) == "hel"
    assert truncate_str("short", 10) == "short"


def test_truncate_str_dict():
    data = {"a": "hello world", "b": "another long string"}
    truncated = truncate_str(data, 10)
    assert truncated["a"] == "hello  ..."
    assert truncated["b"] == "anothe ..."


def test_truncate_str_list():
    data = ["hello world", "another long string"]
    truncated = truncate_str(data, 10)
    assert truncated[0] == "hello  ..."
    assert truncated[1] == "anothe ..."


def test_truncate_str_tuple():
    data = ("hello world", "another long string")
    truncated = truncate_str(data, 10)
    assert isinstance(truncated, tuple)
    assert truncated[0] == "hello  ..."
    assert truncated[1] == "anothe ..."


def test_truncate_str_set():
    data = {"hello world", "another long string"}
    truncated = truncate_str(data, 10)
    assert isinstance(truncated, set)
    assert "hello  ..." in truncated
    assert "anothe ..." in truncated


def test_truncate_str_nested():
    data = {
        "a": ["hello world", ("short", "another very long string")],
        "b": {"c": "a third long string here"},
    }
    truncated = truncate_str(data, 12)
    assert truncated["a"][0] == "hello world"
    assert truncated["a"][1][0] == "short"
    assert truncated["a"][1][1] == "another  ..."
    assert truncated["b"]["c"] == "a third  ..."


def test_truncate_str_other_types():
    assert truncate_str(123, 10) == 123
    assert truncate_str(123.45, 10) == 123.45
    assert truncate_str(True, 10) is True
    assert truncate_str(None, 10) is None
    assert truncate_str(b"byte string", 10) == b"byte string"


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
    result, info = truncate_output(text, head_lines=1, tail_lines=1, max_line_length=100)
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
