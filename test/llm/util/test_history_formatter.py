"""Tests for the history_formatter module."""

from datetime import datetime, timezone

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.util.history_formatter import (
    _format_args,
    _format_timestamp,
    _indent_lines,
    _truncate,
    format_history_as_text,
)


class TestFormatHistoryAsText:
    """Tests for format_history_as_text function."""

    def test_empty_history(self):
        """Test formatting empty history."""
        result = format_history_as_text([])
        assert "Empty conversation history" in result

    def test_single_user_message(self):
        """Test formatting a single user message."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Hello, world!")]),
        ]
        result = format_history_as_text(messages)
        assert "💬" in result
        assert "Hello, world!" in result

    def test_single_assistant_response(self):
        """Test formatting a single assistant response."""
        messages = [
            ModelResponse(parts=[TextPart(content="Hello! How can I help?")]),
        ]
        result = format_history_as_text(messages)
        assert "🤖" in result
        assert "Hello! How can I help?" in result

    def test_conversation_flow(self):
        """Test formatting a back-and-forth conversation."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="What is Python?")]),
            ModelResponse(
                parts=[TextPart(content="Python is a programming language.")]
            ),
            ModelRequest(parts=[UserPromptPart(content="Thank you!")]),
            ModelResponse(parts=[TextPart(content="You're welcome!")]),
        ]
        result = format_history_as_text(messages)

        assert "💬" in result
        assert "What is Python?" in result
        assert "🤖" in result
        assert "Python is a programming language." in result
        assert "Thank you!" in result
        assert "You're welcome!" in result

    def test_tool_call_formatting(self):
        """Test formatting tool calls."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="List files")]),
            ModelResponse(
                parts=[ToolCallPart(tool_name="list_files", args={"path": "."})]
            ),
        ]
        result = format_history_as_text(messages)

        # Uses 🧰 emoji for tool calls (mimicking streaming style)
        assert "🧰" in result
        assert "list_files" in result

    def test_tool_return_formatting(self):
        """Test formatting tool returns."""
        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="list_files",
                        content="file1.py\nfile2.py",
                        outcome="success",
                    ),
                    UserPromptPart(content="What about .txt files?"),
                ]
            ),
            ModelResponse(parts=[TextPart(content="Here are .txt files:")]),
        ]
        result = format_history_as_text(messages)

        # Uses 🔠 emoji for tool returns (mimicking streaming style)
        assert "🔠" in result
        assert "list_files" in result
        assert "file1.py" in result

    def test_system_prompt_formatting(self):
        """Test formatting system prompts."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="You are a helpful assistant."),
                    UserPromptPart(content="Hi!"),
                ]
            ),
        ]
        result = format_history_as_text(messages)

        assert "System Prompt" in result
        assert "You are a helpful assistant." in result

    def test_thinking_part_formatting(self):
        """Test formatting thinking parts."""
        messages = [
            ModelResponse(
                parts=[
                    ThinkingPart(content="Let me think about this..."),
                    TextPart(content="Here's my answer."),
                ]
            ),
        ]
        result = format_history_as_text(messages)

        assert "Thinking" in result
        assert "Let me think about this..." in result

    def test_max_length_truncation(self):
        """Test that output is truncated at max_length."""
        long_content = "x" * 1000
        messages = [
            ModelRequest(parts=[UserPromptPart(content=long_content)]),
        ]

        result = format_history_as_text(messages, max_length=100)
        assert len(result) <= 150  # Allow some margin for truncation message
        assert "truncated" in result

    def test_multiline_content(self):
        """Test formatting multiline content."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Line 1\nLine 2\nLine 3")]),
        ]
        result = format_history_as_text(messages)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_model_name_display(self):
        """Test that model name is displayed in response."""
        messages = [
            ModelResponse(parts=[TextPart(content="Hello!")], model_name="gpt-4"),
        ]
        result = format_history_as_text(messages)

        assert "Model:" in result
        assert "gpt-4" in result


class TestFormatTimestamp:
    """Tests for _format_timestamp function."""

    def test_none_timestamp(self):
        """Test with None timestamp."""
        assert _format_timestamp(None) == ""

    def test_datetime_object(self):
        """Test with datetime object."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = _format_timestamp(dt)
        assert "10:30" in result

    def test_iso_string_timestamp(self):
        """Test with ISO string timestamp."""
        iso_string = "2024-01-15T10:30:45Z"
        result = _format_timestamp(iso_string)
        assert "10:30" in result


class TestFormatArgs:
    """Tests for _format_args function."""

    def test_none_args(self):
        """Test with None args."""
        assert _format_args(None) == "{}"

    def test_string_args(self):
        """Test with string args."""
        result = _format_args("raw string")
        # Should truncate long strings
        assert "raw" in result

    def test_dict_args(self):
        """Test with dict args."""
        args = {"path": ".", "recursive": True}
        result = _format_args(args)
        assert "path" in result
        assert "recursive" in result


class TestIndentLines:
    """Tests for _indent_lines function."""

    def test_single_line(self):
        """Test indenting a single line."""
        lines = _indent_lines("Hello", indent=2)
        assert lines == ["  Hello"]

    def test_multiline(self):
        """Test indenting multiple lines."""
        lines = _indent_lines("Line 1\nLine 2", indent=4)
        assert lines == ["    Line 1", "    Line 2"]

    def test_max_lines_truncation(self):
        """Test that content is truncated at max_lines."""
        content = "\n".join([f"Line {i}" for i in range(100)])
        lines = _indent_lines(content, indent=0, max_lines=10)
        assert len(lines) == 11  # 10 lines + truncation message
        assert "more lines" in lines[-1]


class TestTruncate:
    """Tests for _truncate function."""

    def test_short_text(self):
        """Test with short text."""
        assert _truncate("Hello", max_length=10) == "Hello"

    def test_long_text(self):
        """Test with long text."""
        result = _truncate("Hello World This is a Long Text", max_length=15)
        assert len(result) == 15
        assert result.endswith("...")
