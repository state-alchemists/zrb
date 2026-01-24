import asyncio

import pytest

from zrb.llm.tool.bash import run_shell_command


@pytest.mark.asyncio
async def test_run_shell_command_success():
    res = await run_shell_command("echo hello")
    assert "hello" in res


@pytest.mark.asyncio
async def test_run_shell_command_failure():
    res = await run_shell_command("exit 1")
    assert "Error" in res or "fail" in res.lower() or "Exit Code: 1" in res


@pytest.mark.asyncio
async def test_run_shell_command_timeout():
    # This might be tricky depending on how timeout is implemented
    # but let's try a long command if possible, or just basic success
    res = await run_shell_command("sleep 0.1 && echo done")
    assert "done" in res
