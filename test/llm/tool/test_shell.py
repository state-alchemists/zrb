import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.sandbox.os_sandbox import SandboxUnavailableError
from zrb.llm.tool import shell as shell_mod
from zrb.llm.tool.shell import run_shell_command


class _MockStreamReader:
    """Fake asyncio.StreamReader that yields preset lines then EOF."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines
        self._pos = 0

    async def readline(self) -> bytes:
        if self._pos < len(self._lines):
            line = self._lines[self._pos]
            self._pos += 1
            return line
        return b""


def _make_mock_process(
    stdout_lines: list[str] | None = None,
    stderr_lines: list[str] | None = None,
    returncode: int = 0,
    pid: int = 12345,
) -> MagicMock:
    """Build a mock asyncio.subprocess.Process with readable streams."""
    proc = MagicMock()
    proc.stdout = _MockStreamReader(
        [(s.encode() if isinstance(s, str) else s) for s in (stdout_lines or [])]
    )
    proc.stderr = _MockStreamReader(
        [(s.encode() if isinstance(s, str) else s) for s in (stderr_lines or [])]
    )
    proc.wait = AsyncMock(return_value=returncode)
    proc.returncode = returncode
    proc.pid = pid
    return proc


def test_shell_name():
    assert run_shell_command.__name__ == "Shell"


@pytest.mark.asyncio
async def test_run_shell_command_default_shell(monkeypatch):
    # With no explicit shell, Shell runs under CFG.SHELL (the detected shell).
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


@pytest.mark.asyncio
async def test_run_shell_command_runtime_shell_skips_pid_tracking(monkeypatch):
    # A language runtime (shell="node") resolves a non "-c" flag, so PID
    # tracking is skipped and the command is treated as source code.
    # Mock the subprocess so the test doesn't require node installed
    # (GitLab CI runners may not ship it).
    mock_proc = _make_mock_process(stdout_lines=["runtime-ok\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )
    res = await run_shell_command("console.log('runtime-ok')", shell="node")
    assert "runtime-ok" in res
    assert "Exit Code: 0" in res


@pytest.mark.asyncio
async def test_run_shell_command_invalid_cwd_returns_error():
    # A non-existent cwd makes the subprocess launch fail; the generic
    # exception handler reports it (and cleans up the temp PID file).
    res = await run_shell_command("echo hi", cwd="/nonexistent/zrb/path/xyz")
    assert "Error executing command:" in res
    assert "[SYSTEM SUGGESTION]" in res


@pytest.mark.asyncio
async def test_run_shell_command_background_sandbox_refused(monkeypatch):
    # When the background registry refuses on sandbox policy, the tool relays a
    # sandbox-policy refusal instead of a handle.
    class _RefusingRegistry:
        async def start(self, *args, **kwargs):
            raise SandboxUnavailableError("no sandbox here")

    monkeypatch.setattr(
        "zrb.llm.tool.shell_background.get_shell_background_registry",
        lambda: _RefusingRegistry(),
    )
    res = await run_shell_command("sleep 1", background=True)
    assert "refused by sandbox policy" in res
    assert "no sandbox here" in res
    assert "Handle:" not in res


@pytest.mark.asyncio
async def test_run_shell_command_background_returns_handle(monkeypatch):
    # On success the background path returns a MonitorProcess handle.
    class _OkRegistry:
        async def start(self, *args, **kwargs):
            return "abc123"

    monkeypatch.setattr(
        "zrb.llm.tool.shell_background.get_shell_background_registry",
        lambda: _OkRegistry(),
    )
    res = await run_shell_command("sleep 1", background=True)
    assert "Handle: abc123" in res
    assert "MonitorProcess" in res


@pytest.mark.asyncio
async def test_run_shell_command_foreground_sandbox_deny(monkeypatch):
    # A deny-mode sandbox raises while building the argv; the tool relays the
    # refusal and still cleans up the temp PID file (even if removal fails).
    def _deny(*args, **kwargs):
        raise SandboxUnavailableError("deny mode")

    def _boom(*args, **kwargs):
        raise OSError("cannot remove")

    monkeypatch.setattr("zrb.llm.sandbox.build_sandboxed_argv", _deny)
    monkeypatch.setattr(shell_mod.os, "remove", _boom)
    res = await run_shell_command("echo hi")
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_run_shell_command_truncates_and_dumps(monkeypatch):
    # Output exceeding max_chars is truncated (tail kept) and the full output is
    # dumped to a temp file whose path is reported.
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 5)
    res = await run_shell_command("echo abcdefghijklmnop")
    assert "Output truncated" in res
    assert "saved to" in res


@pytest.mark.asyncio
async def test_run_shell_command_dump_failure_is_best_effort(monkeypatch):
    # If persisting the full output fails, no dump path is reported but the
    # (truncated) result is still returned. shell="node" skips PID tracking so
    # the mkstemp patch only affects the dump path.
    # Mock the subprocess so the test doesn't require node installed.
    def _boom(*args, **kwargs):
        raise OSError("no temp for you")

    mock_proc = _make_mock_process(stdout_lines=["x" * 100 + "\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )
    monkeypatch.setattr(shell_mod.tempfile, "mkstemp", _boom)
    res = await run_shell_command(
        "console.log('x'.repeat(100))", shell="node", max_chars=5
    )
    assert "saved to" not in res
    assert "Exit Code:" in res


@pytest.mark.asyncio
async def test_run_shell_command_timeout():
    # A command that outruns its timeout is terminated; the result reports the
    # timeout, the "(timed out)" exit code, and a follow-up suggestion.
    res = await run_shell_command("sleep 5", timeout=1)
    assert "timed out" in res
    assert "(timed out)" in res
    assert "[SYSTEM SUGGESTION]" in res


@pytest.mark.asyncio
async def test_run_shell_command_survives_long_single_line():
    # Regression: asyncio's default 64KB StreamReader limit made readline()
    # raise on one long line (minified JS, single-line JSON), losing all output
    # and leaving the process running detached.
    res = await run_shell_command(
        "python3 -c \"print('x' * 200000)\"", max_chars=300000
    )
    assert "Exit Code: 0" in res
    assert "xxxx" in res
    assert "Error executing command" not in res


@pytest.mark.asyncio
async def test_run_shell_command_pid_file_cleanup_failure_is_ignored(monkeypatch):
    # Collecting background PIDs is best-effort: a failure removing the temp PID
    # file is swallowed and the command result is still returned.
    real_remove = shell_mod.os.remove

    def _boom(path):
        if "zrb_pids_" in str(path):
            raise OSError("cannot remove pid file")
        return real_remove(path)

    monkeypatch.setattr(shell_mod.os, "remove", _boom)
    res = await run_shell_command("echo cleanup-ok")
    assert "cleanup-ok" in res
    assert "Exit Code: 0" in res
