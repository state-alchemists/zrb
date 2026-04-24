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
    assert "Exit Code: 1" in res


@pytest.mark.asyncio
async def test_run_shell_command_timeout():
    # Verify timeout logic and system suggestion
    result = await run_shell_command("sleep 5", timeout=0.1)
    assert "(timed out)" in result
    assert "[SYSTEM SUGGESTION]" in result


@pytest.mark.asyncio
async def test_run_shell_command_suggestions():
    # Verify suggestions for common shell errors
    result = await run_shell_command("echo 'permission denied'")
    assert "Permission denied" in result

    result = await run_shell_command("echo 'lock' && echo 'brew install ...'")
    assert "package manager lock" in result


@pytest.mark.asyncio
async def test_run_shell_command_suggestion_port_in_use():
    result = await run_shell_command("echo 'address already in use'")
    assert "port is already in use" in result.lower()


@pytest.mark.asyncio
async def test_run_shell_command_suggestion_eaddrinuse():
    result = await run_shell_command("echo 'EADDRINUSE'")
    assert "port is already in use" in result.lower()


@pytest.mark.asyncio
async def test_run_shell_command_suggestion_command_not_found():
    result = await run_shell_command("echo 'command not found'")
    assert "Command not found" in result


@pytest.mark.asyncio
async def test_run_shell_command_suggestion_module_not_found():
    result = await run_shell_command("echo 'No module named foo'")
    assert "Python module not found" in result


@pytest.mark.asyncio
async def test_run_shell_command_suggestion_connection_refused():
    result = await run_shell_command("echo 'connection refused'")
    assert "Connection refused" in result
