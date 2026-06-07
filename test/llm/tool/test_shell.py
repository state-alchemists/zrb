import pytest

from zrb.config.config import CFG
from zrb.llm.tool.shell import run_shell_command


def test_shell_name():
    assert run_shell_command.__name__ == "Shell"


@pytest.mark.asyncio
async def test_run_shell_command_uses_os_default_shell(monkeypatch):
    # With no configured shell, Shell must fall back to the always-present OS
    # default (/bin/sh, cmd.exe) rather than a possibly-absent bash/zsh.
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_SHELL", raising=False)
    monkeypatch.setattr(CFG, "DEFAULT_SHELL", "")
    res = await run_shell_command("echo default-shell")
    assert "default-shell" in res
    assert "Exit Code: 0" in res


@pytest.mark.asyncio
async def test_run_shell_command_success():
    res = await run_shell_command("echo hello")
    assert "hello" in res


@pytest.mark.asyncio
async def test_run_shell_command_failure():
    res = await run_shell_command("exit 1")
    assert "Exit Code: 1" in res


@pytest.mark.asyncio
async def test_run_shell_command_with_sh_shell():
    res = await run_shell_command("echo hello", shell="sh")
    assert "hello" in res


@pytest.mark.asyncio
async def test_run_shell_command_with_sh_shell_failure():
    res = await run_shell_command("exit 42", shell="sh")
    assert "Exit Code: 42" in res


@pytest.mark.asyncio
async def test_run_shell_command_with_bash_shell():
    res = await run_shell_command("echo hello", shell="bash")
    assert "hello" in res


@pytest.mark.asyncio
async def test_run_shell_command_with_bash_shell_bashism():
    # `[[ ... ]]` is bash-only syntax; it errors under POSIX sh/dash.
    res = await run_shell_command("[[ 1 == 1 ]] && echo matched", shell="bash")
    assert "matched" in res
    assert "Exit Code: 0" in res


@pytest.mark.asyncio
async def test_run_shell_command_reports_background_pids():
    # A backgrounded process that outlives the shell is reported so the agent
    # can track it. Uses the default (POSIX) shell where PID tracking applies.
    res = await run_shell_command("sleep 3 & echo started")
    assert "started" in res
    assert "Background PIDs:" in res


@pytest.mark.asyncio
async def test_run_shell_command_stdin_does_not_hang():
    # stdin is DEVNULL, so a command reading stdin returns immediately at EOF
    # instead of hanging until the timeout.
    res = await run_shell_command("cat", timeout=5)
    assert "Exit Code: 0" in res
