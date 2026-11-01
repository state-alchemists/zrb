"""Test bash_safe_command_policy for auto-approving safe read-only commands."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.tool_call.tool_policy.bash_validation import (
    bash_safe_command_policy,
    is_safe_command,
)


class TestIsSafeCommand:
    """Test is_safe_command function."""

    def test_safe_command_ls(self):
        """Test that ls is recognized as safe."""
        assert is_safe_command("ls") is True
        assert is_safe_command("ls -la") is True
        assert is_safe_command("ls /tmp") is True

    def test_safe_command_git_status(self):
        """Test that git status is recognized as safe."""
        assert is_safe_command("git status") is True
        assert is_safe_command("git status -s") is True

    def test_safe_command_cat(self):
        """Test that cat is recognized as safe."""
        assert is_safe_command("cat file.txt") is True

    def test_safe_command_echo(self):
        """Test that echo is recognized as safe."""
        assert is_safe_command("echo hello") is True
        assert is_safe_command("echo 'hello world'") is True

    def test_safe_command_version_queries(self):
        """Test that version queries are recognized as safe."""
        assert is_safe_command("python --version") is True
        assert is_safe_command("node --version") is True
        assert is_safe_command("docker --version") is True

    def test_unsafe_command_with_redirect(self):
        """Test that redirects are rejected."""
        assert is_safe_command("echo hello > file.txt") is False
        assert is_safe_command("cat file > out") is False

    def test_unsafe_command_with_pipe(self):
        """Test that pipes are rejected."""
        assert is_safe_command("cat file | grep pattern") is False
        assert is_safe_command("ls | head") is False

    def test_unsafe_command_with_semicolon(self):
        """Test that semicolons are rejected."""
        assert is_safe_command("ls ; rm -rf /") is False

    def test_unsafe_command_with_and(self):
        """Test that && is rejected."""
        assert is_safe_command("ls && echo done") is False

    def test_unsafe_command_with_single_ampersand(self):
        """Test that a single & (backgrounding/chaining) is rejected."""
        assert is_safe_command("ls & rm -rf x") is False
        assert is_safe_command("ls &") is False

    def test_unsafe_command_with_newline(self):
        """Test that newline/carriage-return separated commands are rejected."""
        assert is_safe_command("ls\nrm x") is False
        assert is_safe_command("ls\r\nrm x") is False

    def test_unsafe_command_env_runs_arbitrary_command(self):
        """`env` is not safe: `env FOO=1 rm -rf x` executes an arbitrary command."""
        assert is_safe_command("env FOO=1 rm -rf x") is False
        assert is_safe_command("env rm -rf x") is False

    def test_safe_command_printenv_still_allowed(self):
        """printenv is a pure read and remains allowlisted."""
        assert is_safe_command("printenv") is True
        assert is_safe_command("printenv PATH") is True

    def test_unsafe_command_with_backtick(self):
        """Test that backticks are rejected."""
        assert is_safe_command("echo `date`") is False

    def test_unsafe_command_with_subshell(self):
        """Test that $() subshells are rejected."""
        assert is_safe_command("echo $(date)") is False

    @pytest.mark.parametrize(
        "command",
        [
            "cat <(touch /tmp/marker)",
            "grep x <(cmd)",
            "head -n 1 <( cmd )",
            "echo <(cmd)",
        ],
    )
    def test_unsafe_command_with_process_substitution(self, command):
        """`<(cmd)` runs cmd, so an allowlisted prefix must not hide it."""
        assert is_safe_command(command) is False

    def test_input_redirection_from_a_file_stays_safe(self):
        """`< file` only reads, so it is not treated like `<(cmd)`."""
        assert is_safe_command("grep x < notes.txt") is True

    def test_unsafe_command_rm(self):
        """Test that rm is not in safe list."""
        assert is_safe_command("rm file.txt") is False

    def test_unsafe_command_mkdir(self):
        """Test that mkdir is not in safe list."""
        assert is_safe_command("mkdir newdir") is False

    def test_unsafe_command_arbitrary(self):
        """Test that arbitrary commands are rejected."""
        assert is_safe_command("some-random-command") is False

    def test_safe_command_case_insensitive(self):
        """Test that safe commands are case-insensitive."""
        assert is_safe_command("LS") is True
        assert is_safe_command("LS -la") is True
        assert is_safe_command("GIT STATUS") is True

    def test_safe_command_with_leading_spaces(self):
        """Test that leading spaces are handled."""
        assert is_safe_command("  ls") is True
        assert is_safe_command("\tls") is True

    def test_safe_command_with_trailing_spaces(self):
        """Test that trailing spaces are handled."""
        assert is_safe_command("ls  ") is True
        assert is_safe_command("ls\t") is True

    def test_empty_command(self):
        """Test that empty command is rejected."""
        assert is_safe_command("") is False
        assert is_safe_command("   ") is False

    def test_git_write_commands_not_safe(self):
        """Test that git write commands are not in safe list."""
        assert is_safe_command("git add") is False
        assert is_safe_command("git commit") is False
        assert is_safe_command("git push") is False


class TestBashSafeCommandPolicy:
    """Test bash_safe_command_policy function."""

    @pytest.mark.asyncio
    async def test_policy_approves_safe_command(self):
        """Test that safe commands are auto-approved."""
        from pydantic_ai import ToolApproved

        policy = bash_safe_command_policy()
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Shell"
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
        call.tool_name = "Shell"
        call.args = {"command": "rm file.txt"}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Unsafe commands should call next_handler
        assert result == "next_result"
        assert next_handler.called is True

    @pytest.mark.asyncio
    async def test_policy_passes_through_non_shell_tool(self):
        """Test that non-Shell tools pass through."""
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
        call.tool_name = "Shell"
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
        call.tool_name = "Shell"
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
        call.tool_name = "Shell"
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
        call.tool_name = "Shell"
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
        call.tool_name = "Shell"
        call.args = {"command": 123}

        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        # Should fall through to next handler
        assert result == "next_result"
        assert next_handler.called is True


# Forms of allowlisted commands that run a program or write a file.
_FLAG_LEAKS = [
    "rg --pre cat pattern",
    "rg --pre=cat pattern",
    "rg --pre-glob '*.txt' pattern",
    "rg --pre-glob=*.txt pattern",
    "rg --hostname-bin=hostname pattern",
    "rg pattern --pre ./evil.sh",
    "git log --output=out.txt",
    "git diff --output out.txt",
    "git show --output=out.txt HEAD",
    "git diff --out=out.txt",
    "git diff --ext-diff",
    "git log --ext-diff -p",
    "git show --textconv HEAD:file",
    "git log -p --textconv",
    "git diff --ext HEAD",
    "sort -o out.txt in.txt",
    "sort -uo out.txt in.txt",
    "sort -oout.txt in.txt",
    "sort --output=out.txt in.txt",
    "sort --output out.txt in.txt",
    "sort --out=out.txt in.txt",
    "sort -S 1 --compress-program=sh in.txt",
    "uniq in.txt out.txt",
    "uniq -c in.txt out.txt",
    "uniq -f 1 in.txt out.txt",
    "uniq -f1 in.txt out.txt",
    "uniq --skip-fields 1 in.txt out.txt",
    "uniq -- in.txt out.txt",
    "uniq - out.txt",
    "file -C",
    "file -C -m magic",
    "file -bC",
    "file --compile",
    "file --comp",
    # Quoting or expansion that hides the option from a plain text match.
    "rg '--pre'=cat pattern",
    'rg --p""re=cat pattern',
    "rg --pr${UNSET}e=cat pattern",
    "rg ${UNSET:---pre=cat} pattern",
    "rg --pr{e,x}=cat pattern",
    "rg {--pre=cat,x} pattern",
    "rg --pre='unterminated pattern",
]

# Harmless forms of the same commands that stay auto-approved.
_HARMLESS_FORMS = [
    "rg pattern",
    "rg -n -i pattern src",
    "rg --no-pre pattern",
    "rg --pretty pattern",
    "rg -e pattern -- --pre",
    "git diff",
    "git diff HEAD~1 -- src",
    "git diff --stat",
    "git diff --no-ext-diff",
    "git diff --no-textconv",
    "git diff --output-indicator-new=+",
    "git log --oneline -n 5",
    "git log HEAD@{1}..HEAD",
    "git show HEAD:README.md",
    "git show --stat",
    "sort file",
    "sort -n -r file",
    "sort -u -k 2,2 file",
    "sort -t, -k2 file",
    "sort -T/tmp/scratch file",
    "sort --reverse file",
    "uniq file",
    "uniq -c file",
    "uniq -f 1 file",
    "uniq -f1 file",
    "uniq --skip-fields 1 file",
    "uniq --skip-fields=1 file",
    "uniq -i -d",
    "uniq",
    "file photo.png",
    "file -b photo.png",
    "file --mime-type photo.png",
    "file -m magic photo.png",
    "file -i a b",
]


class TestFlagsThatRunProgramsOrWriteFiles:
    """An allowlisted command with such a flag needs the normal approval prompt."""

    @pytest.mark.parametrize("command", _FLAG_LEAKS)
    def test_unsafe_form_is_not_auto_approved(self, command):
        assert is_safe_command(command) is False

    @pytest.mark.parametrize("command", _HARMLESS_FORMS)
    def test_harmless_form_stays_auto_approved(self, command):
        assert is_safe_command(command) is True

    @pytest.mark.asyncio
    async def test_policy_hands_unsafe_form_to_the_prompt(self):
        policy = bash_safe_command_policy()
        call = MagicMock()
        call.tool_name = "Shell"
        call.args = {"command": "rg --pre ./evil.sh pattern"}
        next_handler = AsyncMock(return_value="prompted")

        result = await policy(MagicMock(), call, next_handler)

        assert result == "prompted"
        assert next_handler.called is True
