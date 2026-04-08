"""Test bash_safe_command_policy for auto-approving safe read-only commands."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.tool_call.tool_policy.bash_validation import (
    _DANGEROUS_SUBSTRINGS,
    _SAFE_PREFIXES,
    _is_safe_command,
    bash_safe_command_policy,
)


class TestIsSafeCommand:
    """Test _is_safe_command function."""

    def test_safe_command_ls(self):
        """Test that ls is recognized as safe."""
        assert _is_safe_command("ls") is True
        assert _is_safe_command("ls -la") is True
        assert _is_safe_command("ls /tmp") is True

    def test_safe_command_git_status(self):
        """Test that git status is recognized as safe."""
        assert _is_safe_command("git status") is True
        assert _is_safe_command("git status -s") is True

    def test_safe_command_cat(self):
        """Test that cat is recognized as safe."""
        assert _is_safe_command("cat file.txt") is True

    def test_safe_command_echo(self):
        """Test that echo is recognized as safe."""
        assert _is_safe_command("echo hello") is True
        assert _is_safe_command("echo 'hello world'") is True

    def test_safe_command_version_queries(self):
        """Test that version queries are recognized as safe."""
        assert _is_safe_command("python --version") is True
        assert _is_safe_command("node --version") is True
        assert _is_safe_command("docker --version") is True

    def test_unsafe_command_with_redirect(self):
        """Test that redirects are rejected."""
        assert _is_safe_command("echo hello > file.txt") is False
        assert _is_safe_command("cat file > out") is False

    def test_unsafe_command_with_pipe(self):
        """Test that pipes are rejected."""
        assert _is_safe_command("cat file | grep pattern") is False
        assert _is_safe_command("ls | head") is False

    def test_unsafe_command_with_semicolon(self):
        """Test that semicolons are rejected."""
        assert _is_safe_command("ls ; rm -rf /") is False

    def test_unsafe_command_with_and(self):
        """Test that && is rejected."""
        assert _is_safe_command("ls && echo done") is False

    def test_unsafe_command_with_backtick(self):
        """Test that backticks are rejected."""
        assert _is_safe_command("echo `date`") is False

    def test_unsafe_command_with_subshell(self):
        """Test that $() subshells are rejected."""
        assert _is_safe_command("echo $(date)") is False

    def test_unsafe_command_rm(self):
        """Test that rm is not in safe list."""
        assert _is_safe_command("rm file.txt") is False

    def test_unsafe_command_mkdir(self):
        """Test that mkdir is not in safe list."""
        assert _is_safe_command("mkdir newdir") is False

    def test_unsafe_command_arbitrary(self):
        """Test that arbitrary commands are rejected."""
        assert _is_safe_command("some-random-command") is False

    def test_safe_command_case_insensitive(self):
        """Test that safe commands are case-insensitive."""
        assert _is_safe_command("LS") is True
        assert _is_safe_command("LS -la") is True
        assert _is_safe_command("GIT STATUS") is True

    def test_safe_command_with_leading_spaces(self):
        """Test that leading spaces are handled."""
        assert _is_safe_command("  ls") is True
        assert _is_safe_command("\tls") is True

    def test_safe_command_with_trailing_spaces(self):
        """Test that trailing spaces are handled."""
        assert _is_safe_command("ls  ") is True
        assert _is_safe_command("ls\t") is True

    def test_empty_command(self):
        """Test that empty command is rejected."""
        assert _is_safe_command("") is False
        assert _is_safe_command("   ") is False

    def test_git_write_commands_not_safe(self):
        """Test that git write commands are not in safe list."""
        assert _is_safe_command("git add") is False
        assert _is_safe_command("git commit") is False
        assert _is_safe_command("git push") is False


class TestBashSafeCommandPolicy:
    """Test bash_safe_command_policy function."""

    @pytest.mark.asyncio
    async def test_policy_approves_safe_command(self):
        """Test that safe commands are auto-approved."""
        from pydantic_ai import ToolApproved

        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = {"command": "ls -la"}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Safe commands return ToolApproved (not calling next_handler)
        assert isinstance(result, ToolApproved)
        assert next_handler.called is False

    @pytest.mark.asyncio
    async def test_policy_passes_through_unsafe_command(self):
        """Test that unsafe commands fall through to next handler."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = {"command": "rm file.txt"}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Unsafe commands should call next_handler
        assert result == "next_result"
        assert next_handler.called is True

    @pytest.mark.asyncio
    async def test_policy_passes_through_non_bash_tool(self):
        """Test that non-Bash tools pass through."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Write"
        call.args = {"path": "/tmp/test.txt", "content": "hello"}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        assert next_handler.called is True

    @pytest.mark.asyncio
    async def test_policy_handles_string_args(self):
        """Test that policy handles JSON string args."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = json.dumps({"command": "ls"})

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Should parse and approve safe command
        from pydantic_ai import ToolApproved

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_policy_handles_invalid_json_args(self):
        """Test that policy handles invalid JSON gracefully."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = "not valid json"

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Should fall through to next handler
        assert result == "next_result"
        assert next_handler.called is True

    @pytest.mark.asyncio
    async def test_policy_handles_non_dict_args(self):
        """Test that policy handles non-dict args gracefully."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = ["list", "of", "args"]

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Should fall through to next handler
        assert result == "next_result"
        assert next_handler.called is True

    @pytest.mark.asyncio
    async def test_policy_handles_missing_command(self):
        """Test that policy handles missing command gracefully."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = {"other_key": "value"}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Should fall through to next handler
        assert result == "next_result"
        assert next_handler.called is True

    @pytest.mark.asyncio
    async def test_policy_handles_non_string_command(self):
        """Test that policy handles non-string command gracefully."""
        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Bash"
        call.args = {"command": 123}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Should fall through to next handler
        assert result == "next_result"
        assert next_handler.called is True


class TestConstants:
    """Test that constants are properly defined."""

    def test_dangerous_substrings_not_empty(self):
        """Test that dangerous substrings list is not empty."""
        assert len(_DANGEROUS_SUBSTRINGS) > 0
        assert ">" in _DANGEROUS_SUBSTRINGS
        assert "|" in _DANGEROUS_SUBSTRINGS
        assert ";" in _DANGEROUS_SUBSTRINGS

    def test_safe_prefixes_not_empty(self):
        """Test that safe prefixes list is not empty."""
        assert len(_SAFE_PREFIXES) > 0
        assert "ls" in _SAFE_PREFIXES
        assert "cat" in _SAFE_PREFIXES
        assert "git status" in _SAFE_PREFIXES
