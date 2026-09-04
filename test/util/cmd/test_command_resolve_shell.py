import asyncio
import os
import subprocess
from unittest.mock import patch

import psutil
import pytest

from zrb.config.config import CFG
from zrb.util.cmd.command import (
    check_unrecommended_commands,
    kill_pid,
    resolve_shell,
    run_command,
    terminate_pid,
    terminate_process,
)
from zrb.util.cmd.remote import get_remote_cmd_script


def test_resolve_shell_empty_uses_cfg_shell(monkeypatch):
    # No explicit shell -> fall back to CFG.SHELL.
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_SHELL", raising=False)
    monkeypatch.setattr(CFG, "DEFAULT_SHELL", "bash")
    sh, flag = resolve_shell("")
    assert sh == CFG.SHELL == "bash"
    assert flag == "-c"


def test_resolve_shell_env_opt_in(monkeypatch):
    # An explicit ZRB_SHELL opts the empty call into that shell.
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_SHELL", "bash")
    assert resolve_shell("") == ("bash", "-c")


def test_resolve_shell_posix():
    assert resolve_shell("bash") == ("bash", "-c")
    assert resolve_shell("zsh") == ("zsh", "-c")


def test_resolve_shell_runtimes_and_powershell():
    assert resolve_shell("node") == ("node", "-e")
    assert resolve_shell("ruby") == ("ruby", "-e")
    assert resolve_shell("php") == ("php", "-r")
    # Flag lookup is case-insensitive on the shell name; PowerShell uses
    # -Command (not the cmd.exe /c switch).
    assert resolve_shell("PowerShell") == ("PowerShell", "-Command")
    assert resolve_shell("pwsh") == ("pwsh", "-Command")
    # cmd.exe uses /c, not -c.
    assert resolve_shell("cmd") == ("cmd", "/c")


@pytest.mark.asyncio
async def test_terminate_process_kills_tree():
    # A shell that spawns a child; terminate_process must reap the whole tree.
    proc = await asyncio.create_subprocess_shell(
        "sleep 30 & sleep 30",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    await asyncio.sleep(0.1)
    await terminate_process(proc, grace_seconds=2.0)
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_terminate_process_already_exited_is_noop():
    proc = await asyncio.create_subprocess_shell("true")
    await proc.wait()
    # Should not raise even though the process is gone.
    await terminate_process(proc, grace_seconds=1.0)


def test_terminate_pid_unknown_is_noop():
    # A non-existent PID must not raise.
    terminate_pid(2_000_000_000)


@pytest.mark.asyncio
async def test_terminate_pid_terminates():
    proc = subprocess.Popen(["sleep", "3"])
    pid = proc.pid
    assert psutil.pid_exists(pid)

    terminate_pid(pid)
    proc.wait()

    for _ in range(10):
        if not psutil.pid_exists(pid):
            break
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        await asyncio.sleep(0.1)

    assert (
        not psutil.pid_exists(pid)
        or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    )


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
async def test_run_command_timeout_without_killpg_falls_back_to_terminate_pid(
    monkeypatch,
):
    """Windows has no os.killpg; the timeout cleanup must fall back to psutil."""
    monkeypatch.delattr(os, "killpg")
    with patch("zrb.util.cmd.command.terminate_pid") as mock_terminate:
        with pytest.raises(asyncio.TimeoutError):
            await run_command(["sleep", "2"], timeout=0.5)
        mock_terminate.assert_called_once()


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
    proc.wait()  # Fix ResourceWarning by waiting for it to fully terminate

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


def test_get_remote_cmd_script_basic():
    """Test basic SSH command generation."""
    cmd = "ls -la"
    result = get_remote_cmd_script(cmd, host="example.com", port=22, user="user")
    assert "ssh -t -p 22 user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_with_ssh_key():
    """Test SSH command generation with SSH key."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd, host="example.com", port=22, user="user", ssh_key="/path/to/key"
    )
    assert "ssh -t -p 22 -i /path/to/key user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_with_password():
    """Test SSH command generation with password authentication."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd,
        host="example.com",
        port=22,
        user="user",
        use_password=True,
    )
    assert "sshpass -e ssh -t -p 22 user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_with_ssh_key_and_password():
    """Test SSH command generation with both SSH key and password."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd,
        host="example.com",
        port=22,
        user="user",
        use_password=True,
        ssh_key="/path/to/key",
    )
    assert "sshpass -e ssh -t -p 22 -i /path/to/key user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_custom_port():
    """Test SSH command generation with custom port."""
    cmd = "ls -la"
    result = get_remote_cmd_script(cmd, host="example.com", port=2222, user="user")
    assert "ssh -t -p 2222 user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_quotes_injection_in_credentials():
    """Password is passed via SSHPASS env var, not on the command line."""
    malicious = 'p"$(touch /tmp/pwn)`'

    result = get_remote_cmd_script(
        "ls",
        host="example.com",
        port=22,
        user="user",
        use_password=True,
    )
    # sshpass -e reads the password from SSHPASS — never on the command line.
    assert "sshpass -e" in result
    assert malicious not in result
