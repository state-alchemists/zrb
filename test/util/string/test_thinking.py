"""Tests for thinking tag removal utilities."""

import pytest

from zrb.util.string.thinking import remove_thinking_tags


def test_basic_thinking_tag_removal():
    """Test basic thinking tag removal."""
    assert (
        remove_thinking_tags("Hello<thinking>I'm thinking</thinking>World")
        == "HelloWorld"
    )
    assert (
        remove_thinking_tags("<thinking>I'm thinking</thinking>Hello World")
        == "Hello World"
    )
    assert (
        remove_thinking_tags("Hello World<thinking>I'm thinking</thinking>")
        == "Hello World"
    )


def test_multiple_thinking_tags():
    """Test removal of multiple thinking tags."""
    assert (
        remove_thinking_tags(
            "A<thinking>think1</thinking>B<thinking>think2</thinking>C"
        )
        == "ABC"
    )


def test_nested_thinking_tags():
    """Test removal of nested thinking tags."""
    assert (
        remove_thinking_tags(
            "Hello<thinking>Outer<thinking>Inner</thinking>Outer</thinking>World"
        )
        == "HelloWorld"
    )
    assert (
        remove_thinking_tags(
            "A<thinking>B<thinking>C<thinking>D</thinking>C</thinking>B</thinking>E"
        )
        == "AE"
    )


def test_thought_tags():
    """Test removal of thought tags."""
    assert (
        remove_thinking_tags(
            "A<thought>thought1</thought>B<thought>thought2</thought>C"
        )
        == "ABC"
    )
    assert (
        remove_thinking_tags("A<thinking>think</thinking>B<thought>thought</thought>C")
        == "ABC"
    )


def test_mixed_nested_tags():
    """Test removal of mixed nested tags."""
    # Note: thinking and thought tags are processed separately, not as a single hierarchy
    assert remove_thinking_tags("A<thinking>B<thought>C</thought>B</thinking>D") == "AD"


def test_unclosed_tags():
    """Test that unclosed tags are preserved as text."""
    assert (
        remove_thinking_tags("Hello<thinking>Unclosed World")
        == "Hello<thinking>Unclosed World"
    )
    assert remove_thinking_tags("Hello</thinking>World") == "Hello</thinking>World"
    assert remove_thinking_tags("Hello<thought>Unclosed") == "Hello<thought>Unclosed"
    assert remove_thinking_tags("Hello</thought>World") == "Hello</thought>World"


def test_empty_tags():
    """Test removal of empty tags."""
    assert remove_thinking_tags("Hello<thinking></thinking>World") == "HelloWorld"
    assert remove_thinking_tags("Hello<thought></thought>World") == "HelloWorld"


def test_tags_with_newlines():
    """Test removal of tags containing newlines."""
    input_text = "Hello\n<thinking>I need to think about this\nLet me consider...</thinking>\nWorld"
    expected = "Hello\n\nWorld"
    assert remove_thinking_tags(input_text) == expected


def test_complex_real_world_example():
    """Test a complex real-world example."""
    input_text = """Before text.
<thinking>
Let me think about this problem step by step.
First, I need to understand what the user is asking.
<thinking>
Actually, let me break this down further.
</thinking>
Now I have a better understanding.
</thinking>
After text.<thought>Quick thought</thought>End."""

    expected = """Before text.

After text.End."""

    assert remove_thinking_tags(input_text) == expected


def test_edge_case_malformed_xml():
    """Test edge case where thinking tag contains </thinking> as text."""
    # This is malformed XML. The first </thinking> is treated as closing tag.
    input_text = "Hello<thinking>Here is </thinking> in my thought</thinking>World"
    result = remove_thinking_tags(input_text)
    # Current behavior: treats first </thinking> as closing tag
    assert result == "Hello in my thought</thinking>World"


def test_edge_case_legitimate_thinking_in_text():
    """Test edge case where legitimate <thinking> appears in text (e.g., discussing XML)."""
    # This looks like a thinking tag, so it's removed
    input_text = "The tag is <thinking> not </thinking> in XML"
    result = remove_thinking_tags(input_text)
    # Current behavior: removes it because it looks like a thinking tag
    assert result == "The tag is  in XML"


def test_performance_large_text():
    """Test performance with large text."""
    # Create a large text with many thinking tags
    parts = []
    for i in range(100):
        parts.append(f"Text {i}<thinking>Thinking {i}</thinking>")
    input_text = "".join(parts)

    # Build expected result
    expected_parts = []
    for i in range(100):
        expected_parts.append(f"Text {i}")
    expected = "".join(expected_parts)

    result = remove_thinking_tags(input_text)
    assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
