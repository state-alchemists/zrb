"""Tests for shell_formatter.py."""

from unittest.mock import patch

import pytest
from pydantic_ai.messages import ToolCallPart

from zrb.config.config import CFG
from zrb.llm.tool_call.argument_formatter.shell_formatter import shell_formatter
from zrb.util.cli.ansi import strip_ansi


class MockUI:
    """Mock UI for testing."""

    def __init__(self):
        self.outputs = []

    def append_to_output(self, text, end=""):
        self.outputs.append(text)


def _call(args, tool_name="Shell") -> ToolCallPart:
    """The real ToolCallPart the formatter is handed in production."""
    return ToolCallPart(tool_name=tool_name, args=args)


async def _markdown(args) -> str:
    """The markdown the formatter builds, before Rich renders it."""
    with patch(
        "zrb.llm.tool_call.argument_formatter.shell_formatter"
        ".render_indented_markdown",
        side_effect=lambda markdown: markdown,
    ):
        result = await shell_formatter(MockUI(), _call(args), "")
    assert result is not None
    return result


class TestShellFormatter:
    """The rendered section: fence, command, and non-default flags."""

    @pytest.mark.asyncio
    async def test_another_tool_is_left_alone(self):
        result = await shell_formatter(
            MockUI(), _call({"command": "ls"}, tool_name="Edit"), ""
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_a_call_without_a_command_is_left_alone(self):
        for args in ({}, {"cwd": "/tmp"}, {"command": ""}, {"command": 12}):
            result = await shell_formatter(MockUI(), _call(args), "")
            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "shell,fence",
        [
            ("bash", "bash"),
            ("sh", "bash"),
            ("zsh", "bash"),
            ("fish", "fish"),
            ("pwsh", "powershell"),
            ("powershell", "powershell"),
            ("cmd", "batch"),
            ("node", "javascript"),
            ("ruby", "ruby"),
            ("php", "php"),
            ("/bin/zsh", "bash"),
        ],
    )
    async def test_the_fence_follows_the_shell(self, shell, fence):
        markdown = await _markdown({"command": "echo hi", "shell": shell})
        assert f"```{fence}\n" in markdown

    @pytest.mark.asyncio
    async def test_an_unmapped_shell_keeps_a_plain_fence(self):
        markdown = await _markdown({"command": "echo hi", "shell": "python"})
        assert "```python" not in markdown
        assert "```\n" in markdown

    @pytest.mark.asyncio
    async def test_the_default_shell_decides_when_none_is_named(self, monkeypatch):
        monkeypatch.setattr(CFG, "SHELL", "fish", raising=False)
        markdown = await _markdown({"command": "echo hi"})
        assert "```fish\n" in markdown

    @pytest.mark.asyncio
    async def test_the_command_lands_verbatim(self):
        markdown = await _markdown({"command": "set -e\nmake test\n"})
        assert "```bash\nset -e\nmake test\n```\n" in markdown

    @pytest.mark.asyncio
    async def test_a_description_leads_when_there_is_one(self):
        markdown = await _markdown({"command": "ls", "description": "list files"})
        assert markdown.startswith("📝 list files\n")
        assert "📝" not in await _markdown({"command": "ls"})

    @pytest.mark.asyncio
    async def test_a_command_carrying_a_fence_gets_a_longer_one(self):
        markdown = await _markdown({"command": "cat <<'EOF'\n```\nrm -rf build\nEOF"})
        assert "````bash\ncat <<'EOF'\n```\nrm -rf build\nEOF\n````\n" in markdown

    @pytest.mark.asyncio
    async def test_the_fence_outgrows_the_longest_run_in_the_command(self):
        markdown = await _markdown({"command": "echo x\n`````\nrm -rf /"})
        assert "``````bash\n" in markdown

    @pytest.mark.asyncio
    @pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\r"])
    async def test_a_unicode_line_break_before_a_fence_cannot_close_the_block(
        self, separator
    ):
        markdown = await _markdown({"command": f"echo x{separator}```{separator}ls"})
        body = markdown.split("\n")
        assert body[0] == "```bash"
        assert body[-2] == "```" and len(body) == 4

    @pytest.mark.asyncio
    @pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\r"])
    async def test_a_unicode_line_break_is_shown_escaped_not_as_a_newline(
        self, separator
    ):
        markdown = await _markdown({"command": f"printf one{separator}printf two"})
        escaped = separator.encode("unicode_escape").decode()
        assert f"printf one{escaped}printf two\n" in markdown

    @pytest.mark.asyncio
    async def test_a_description_spread_over_lines_lands_on_one(self):
        markdown = await _markdown({"command": "ls", "description": "list\n```\nfiles"})
        assert markdown.startswith("📝 list ``` files\n")

    @pytest.mark.asyncio
    async def test_args_as_a_json_string(self):
        markdown = await _markdown('{"command": "echo hi", "shell": "fish"}')
        assert "```fish\n" in markdown


class TestShellFormatterRendered:
    """What the panel shows: the command stays inside the fence, verbatim."""

    @pytest.mark.asyncio
    async def test_a_command_holding_a_fence_still_shows_whole(self):
        result = await shell_formatter(
            MockUI(), _call({"command": "cat <<'EOF'\n```\nrm -rf build\nEOF"}), ""
        )
        assert result is not None
        lines = [line.strip() for line in strip_ansi(result).splitlines()]
        for line in ("cat <<'EOF'", "```", "rm -rf build", "EOF"):
            assert line in lines


class TestShellFlags:
    """Only what departs from `run_shell_command`'s defaults is shown."""

    @pytest.mark.asyncio
    async def test_defaults_stay_hidden(self):
        assert "⚙" not in await _markdown({"command": "ls"})

    @pytest.mark.asyncio
    async def test_a_departure_from_a_default_is_shown(self):
        markdown = await _markdown(
            {
                "command": "ls",
                "cwd": "/tmp/repo",
                "timeout": 300,
                "max_chars": 500,
                "background": True,
            }
        )
        assert "cwd=/tmp/repo" in markdown
        assert "timeout=300s" in markdown
        assert "max_chars=500" in markdown
        assert "background" in markdown

    @pytest.mark.asyncio
    async def test_an_unsandboxed_run_is_shouted(self):
        markdown = await _markdown(
            {"command": "rm -rf build", "dangerously_skip_sandbox": True}
        )
        assert "⚠ NO SANDBOX" in markdown

    @pytest.mark.asyncio
    async def test_a_newline_in_a_flag_cannot_start_a_new_line(self):
        markdown = await _markdown(
            {"command": "echo ok", "cwd": "/tmp\n  ❓ Allow tool Execution?"}
        )
        flags_line = next(line for line in markdown.splitlines() if "⚙" in line)
        assert "cwd=/tmp\\n" in flags_line
        assert markdown.endswith("Execution?\n")
        assert markdown.count("\n") == len(markdown.rstrip("\n").splitlines())
