"""Tests for shell_formatter.py."""

from unittest.mock import patch

import pytest
from pydantic_ai.messages import ToolCallPart

from zrb.config.config import CFG
from zrb.llm.tool_call.argument_formatter.shell_formatter import shell_formatter


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
    async def test_args_as_a_json_string(self):
        markdown = await _markdown('{"command": "echo hi", "shell": "fish"}')
        assert "```fish\n" in markdown


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
