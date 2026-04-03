"""Tests for custom_command.py - Custom command class."""

import pytest

from zrb.llm.custom_command.custom_command import CustomCommand


class TestCustomCommandInit:
    """Test CustomCommand initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        cmd = CustomCommand(
            command="test-command",
            prompt="Test prompt",
        )

        assert cmd.command == "test-command"
        # Verify prompt through get_prompt which returns prompt content
        assert "Test prompt" in cmd.get_prompt({})
        # When args not provided, args returns ["ARGUMENTS"] by default
        assert cmd.args == ["ARGUMENTS"]
        # When description not provided, description returns formatted command
        assert "test-command" in cmd.description

    def test_init_with_args(self):
        """Test initialization with args."""
        cmd = CustomCommand(
            command="test-command",
            prompt="Test prompt",
            args=["arg1", "arg2"],
        )

        assert cmd.args == ["arg1", "arg2"]

    def test_init_with_description(self):
        """Test initialization with description."""
        cmd = CustomCommand(
            command="test-command",
            prompt="Test prompt",
            description="Custom description",
        )

        assert cmd.description == "Custom description"


class TestCustomCommandProperties:
    """Test CustomCommand properties."""

    def test_command_property(self):
        """Test command property returns correct value."""
        cmd = CustomCommand(command="my-command", prompt="prompt")
        assert cmd.command == "my-command"

    def test_description_default(self):
        """Test description default value."""
        cmd = CustomCommand(
            command="test-command",
            prompt="prompt",
            args=["arg1", "arg2"],
        )

        # Should be command + args formatted
        assert "test-command" in cmd.description
        assert "<arg1>" in cmd.description
        assert "<arg2>" in cmd.description

    def test_description_custom(self):
        """Test custom description."""
        cmd = CustomCommand(
            command="test-command",
            prompt="prompt",
            description="My custom description",
        )

        assert cmd.description == "My custom description"

    def test_args_default(self):
        """Test args default value when none provided."""
        cmd = CustomCommand(command="test", prompt="prompt")
        assert cmd.args == ["ARGUMENTS"]

    def test_args_provided(self):
        """Test args when provided."""
        cmd = CustomCommand(
            command="test",
            prompt="prompt",
            args=["file", "output"],
        )
        assert cmd.args == ["file", "output"]


class TestCustomCommandGetPrompt:
    """Test CustomCommand get_prompt method."""

    def test_get_prompt_no_placeholders(self):
        """Test get_prompt with no placeholders."""
        cmd = CustomCommand(
            command="test",
            prompt="This is a simple prompt",
            args=["ARGUMENTS"],
        )

        result = cmd.get_prompt({"input": "hello world"})

        # With no placeholders and no replacement, the prompt is returned as-is
        assert "This is a simple prompt" in result

    def test_get_prompt_with_typed_args(self):
        """Test get_prompt with typed arguments."""
        cmd = CustomCommand(
            command="test",
            prompt="Process $file and $output",
            args=["file", "output"],
        )

        result = cmd.get_prompt({"file": "input.txt", "output": "out.txt"})

        assert "input.txt" in result
        assert "out.txt" in result

    def test_get_prompt_with_default_values(self):
        """Test get_prompt with default values ${name:-default}."""
        cmd = CustomCommand(
            command="test",
            prompt="File: ${file:-default.txt}, Count: ${count:-10}",
            args=["file", "count"],
        )

        # With provided values
        result = cmd.get_prompt({"file": "custom.txt"})
        assert "custom.txt" in result
        assert "10" in result  # Default value for count

    def test_get_prompt_with_braced_variable(self):
        """Test get_prompt with ${name} substitution."""
        cmd = CustomCommand(
            command="test",
            prompt="Path: ${path}",
            args=["path"],
        )

        result = cmd.get_prompt({"path": "/home/user"})
        assert "/home/user" in result

    def test_get_prompt_with_numbered_substitution(self):
        """Test positional argument substitution $1, $2, etc."""
        cmd = CustomCommand(
            command="test",
            prompt="First: $1, Second: $2",
            args=["arg1", "arg2"],
        )

        result = cmd.get_prompt({"arg1": "value1", "arg2": "value2"})
        assert "value1" in result
        assert "value2" in result

    def test_get_prompt_missing_var_keeps_original(self):
        """Test that missing $var keeps the original placeholder."""
        cmd = CustomCommand(
            command="test",
            prompt="File: $missing_var",
            args=["ARGUMENTS"],
        )

        result = cmd.get_prompt({"other": "value"})
        # Missing variable should keep the original
        assert "$missing_var" in result

    def test_get_prompt_with_arg_arguments_mode(self):
        """Test prompt formatting when using ARGUMENTS as args."""
        cmd = CustomCommand(
            command="test",
            prompt="Process the input",
            args=["ARGUMENTS"],
        )

        result = cmd.get_prompt({"ARGUMENTS": "hello world"})
        assert "hello world" in result

    def test_get_prompt_mixed_args(self):
        """Test with multiple argument types."""
        cmd = CustomCommand(
            command="test",
            prompt="Process ${file:-input.txt} with $options",
            args=["file", "options"],
        )

        result = cmd.get_prompt({"options": "--verbose"})
        assert "input.txt" in result  # Default value used for file
        assert "--verbose" in result  # Provided value for options


class TestCustomCommandEdgeCases:
    """Test edge cases in CustomCommand."""

    def test_empty_args_provides_arguments(self):
        """Test that empty args list returns ARGUMENTS."""
        cmd = CustomCommand(
            command="test",
            prompt="prompt",
            args=[],
        )
        assert cmd.args == ["ARGUMENTS"]

    def test_description_with_no_args(self):
        """Test description when no args provided."""
        cmd = CustomCommand(
            command="mycmd",
            prompt="prompt",
            args=[],
        )
        # Should show command with <ARGUMENTS>
        assert "mycmd" in cmd.description
        assert "<ARGUMENTS>" in cmd.description

    def test_get_prompt_empty_kwargs(self):
        """Test get_prompt with empty kwargs."""
        cmd = CustomCommand(
            command="test",
            prompt="Simple prompt",
            args=["ARGUMENTS"],
        )

        result = cmd.get_prompt({})
        # Should still work, may or may not append arguments
        assert "Simple prompt" in result

    def test_get_prompt_special_characters_in_values(self):
        """Test get_prompt handles special characters."""
        cmd = CustomCommand(
            command="test",
            prompt="File: $file",
            args=["file"],
        )

        result = cmd.get_prompt({"file": "/path/to/file with spaces.txt"})
        assert "/path/to/file with spaces.txt" in result


class TestCustomCommandArgOrder:
    """Test argument ordering in CustomCommand."""

    def test_args_order_preserved(self):
        """Test that argument order is preserved."""
        cmd = CustomCommand(
            command="test",
            prompt="$1 then $2 then $3",
            args=["first", "second", "third"],
        )

        result = cmd.get_prompt(
            {
                "first": "A",
                "second": "B",
                "third": "C",
            }
        )

        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_args_for_description_order(self):
        """Test args order in description."""
        cmd = CustomCommand(
            command="test",
            prompt="prompt",
            args=["first", "second", "third"],
        )

        desc = cmd.description
        # Args should appear in order
        first_idx = desc.index("<first>")
        second_idx = desc.index("<second>")
        third_idx = desc.index("<third>")

        assert first_idx < second_idx < third_idx
