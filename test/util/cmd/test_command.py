import asyncio
import os
import subprocess

import psutil
import pytest

from zrb.util.cmd.command import check_unrecommended_commands, kill_pid, run_command


def test_check_unrecommended_commands():
    # Test safe script
    assert check_unrecommended_commands("printf 'hello'") == {}

    # Test banned commands
    violations = check_unrecommended_commands("echo 'hello'")
    assert "echo" in violations
    assert violations["echo"] == "echo isn't consistent across OS; use printf instead"

    violations = check_unrecommended_commands("ls -la")
    assert r"\bls " in violations

    violations = check_unrecommended_commands("cat file | sort -V")
    assert r"sort.*-V" in violations


@pytest.mark.asyncio
async def test_run_command_success():
    cmd = ["printf", "hello"]
    result, return_code = await run_command(cmd)

    assert return_code == 0
    assert result.output.strip() == "hello"
    assert result.error == ""


@pytest.mark.asyncio
async def test_run_command_stderr():
    # Write to stderr
    script = "import sys; print('error', file=sys.stderr)"
    cmd = ["python3", "-c", script]
    result, return_code = await run_command(cmd)

    assert return_code == 0
    assert "error" in result.error.strip()


@pytest.mark.asyncio
async def test_run_command_timeout():
    # Sleep for 2 seconds, but timeout is 0.5s
    cmd = ["sleep", "2"]

    with pytest.raises(asyncio.TimeoutError):
        await run_command(cmd, timeout=0.5)


@pytest.mark.asyncio
async def test_run_command_cwd():
    # Print current working directory
    cmd = ["pwd"]
    cwd = "/tmp"
    result, return_code = await run_command(cmd, cwd=cwd)

    assert return_code == 0
    # Resolving symlinks for /tmp on some systems
    assert os.path.realpath(result.output.strip()) == os.path.realpath(cwd)


@pytest.mark.asyncio
async def test_kill_pid():
    # Start a long running process
    proc = subprocess.Popen(["sleep", "3"])
    pid = proc.pid

    assert psutil.pid_exists(pid)

    kill_pid(pid)

    # Wait for process to terminate
    for _ in range(10):
        if not psutil.pid_exists(pid):
            break
        try:
            p = psutil.Process(pid)
            if p.status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        await asyncio.sleep(0.1)

    assert (
        not psutil.pid_exists(pid)
        or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    )
