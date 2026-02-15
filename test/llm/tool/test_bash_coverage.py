import pytest
import asyncio
from zrb.llm.tool.bash import run_shell_command

@pytest.mark.asyncio
async def test_run_shell_command_timeout():
    # Test timeout logic and suggestion
    result = await run_shell_command("sleep 5", timeout=1)
    assert "(timed out)" in result
    assert "[SYSTEM SUGGESTION]" in result

@pytest.mark.asyncio
async def test_run_shell_command_error():
    # Test execution error
    result = await run_shell_command("exit 1")
    assert "Exit Code: 1" in result

@pytest.mark.asyncio
async def test_run_shell_command_suggestions():
    # Test permission denied suggestion
    result = await run_shell_command("echo 'permission denied'")
    assert "Permission denied" in result
    
    # Test package manager lock suggestion
    # We pass the full command string as the first argument
    result = await run_shell_command("echo 'lock' && echo 'brew install ...'")
    assert "package manager lock" in result
