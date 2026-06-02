import pytest

from zrb.llm.tool.shell import run_shell_command


def test_shell_name():
    assert run_shell_command.__name__ == "Shell"


@pytest.mark.asyncio
async def test_run_shell_command_success():
    res = await run_shell_command("echo hello")
    assert "hello" in res


@pytest.mark.asyncio
async def test_run_shell_command_failure():
    res = await run_shell_command("exit 1")
    assert "Exit Code: 1" in res
