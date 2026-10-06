import os
import re
import shlex
import signal
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import psutil
import pytest

from zrb.config.config import CFG
from zrb.llm.tool import shell as shell_mod
from zrb.llm.tool import stream_capture as capture_mod
from zrb.llm.tool.shell import run_shell_command

# The interpreter running the suite, spelled for a POSIX shell: Windows has no
# `python3` on PATH, and its executable path is full of backslashes the shell
# would read as escapes.
_PYTHON = shlex.quote(Path(sys.executable).as_posix())


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


@pytest.mark.parametrize("shell", ["bash", "sh", ""])
@pytest.mark.parametrize(
    "command, expected",
    [
        # A heredoc: `EOF ; }` stops being a delimiter alone on its line, so the
        # shell swallowed the rest of the wrapper hunting for one.
        (f"{_PYTHON} - <<'EOF'\nprint('heredoc-ok')\nEOF", "heredoc-ok"),
        ("cat <<-EOF\n\tdash-ok\n\tEOF", "dash-ok"),
        # A trailing comment ate the wrapper's own `; }`.
        ("echo comment-ok  # explain the command", "comment-ok"),
        # A trailing newline or `;` produced `; ; }` — a syntax error on bash/sh.
        ("echo newline-ok\n", "newline-ok"),
        ("echo semicolon-ok;", "semicolon-ok"),
    ],
)
@pytest.mark.asyncio
async def test_pid_tracking_wrapper_preserves_command_syntax(command, expected, shell):
    res = await run_shell_command(command, shell=shell)
    assert expected in res
    assert "Exit Code: 0" in res


@pytest.mark.asyncio
async def test_pid_tracking_wrapper_preserves_exit_code():
    """The wrapper reports the command's status."""
    res = await run_shell_command("exit 7")
    assert "Exit Code: 7" in res


@pytest.mark.asyncio
async def test_empty_command_is_a_no_op_not_a_syntax_error():
    """Empty commands skip the wrapper and succeed."""
    res = await run_shell_command("   ")
    assert "Exit Code: 0" in res


@pytest.mark.skipif(os.name != "posix", reason="PID tracking is POSIX-only")
@pytest.mark.asyncio
async def test_run_shell_command_reports_background_pids():
    # A backgrounded process that outlives the shell is reported so the agent
    # can track it, and left running. It holds the output pipes open, yet the
    # call returns once the shell exits instead of running into the timeout.
    # Uses the default (POSIX) shell where PID tracking applies.
    start = time.monotonic()
    res = await run_shell_command("sleep 30 & echo started", timeout=4)
    elapsed = time.monotonic() - start
    pids = [
        int(p) for p in re.findall(r"Background PIDs: ([\d, ]+)", res)[0].split(",")
    ]
    try:
        assert "started" in res and "Exit Code: 0" in res
        assert elapsed < 3
        assert all(psutil.pid_exists(pid) for pid in pids)
    finally:
        for pid in pids:
            os.kill(pid, signal.SIGKILL)


@pytest.mark.skipif(os.name != "posix", reason="background shell syntax is POSIX-only")
@pytest.mark.asyncio
async def test_run_shell_command_reports_discarded_background_output():
    res = await run_shell_command("(sleep 1; echo LATE) &", timeout=4)

    assert "[zrb] output not fully captured" in res
    assert "Exit Code: 0" in res


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
        f"{_PYTHON} -c \"print('x' * 200000)\"", max_chars=300000
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


def test_timeout_docstring_states_seconds_not_milliseconds():
    """The unit must be explicit in the description the model reads.

    Every other agent-shell tool in wide use takes milliseconds (default
    120000), so a bare `timeout: int = 120` invites millisecond values. One
    benchmarked model passed 15000 meaning 15s, got 15000 seconds, and its
    otherwise-perfect run was recorded as a timeout.

    Checked against the `timeout` parameter's own schema description (not the
    tool-level docstring) — that is the text pydantic-ai actually surfaces
    next to the field the model is filling in; see ADR-0055's amendment on
    per-parameter schema binding.
    """
    from pydantic_ai import Tool

    desc = Tool(run_shell_command).function_schema.json_schema["properties"]["timeout"][
        "description"
    ]

    assert "SECONDS" in desc
    assert "not milliseconds" in desc


def test_timeout_docstring_points_long_running_work_at_background():
    """Large timeouts should point callers to background execution."""
    from pydantic_ai import Tool

    desc = Tool(run_shell_command).function_schema.json_schema["properties"][
        "background"
    ]["description"]

    assert "long-running" in desc
    assert "server" in desc


def test_docstring_points_unbounded_output_at_a_summarizing_form():
    """Unbounded output should point callers to bounded commands."""
    doc = run_shell_command.__doc__ or ""

    assert "--stat" in doc
    assert "timeout" in doc


@pytest.mark.asyncio
async def test_full_output_survives_bounded_memory_retention(monkeypatch):
    """The spill file preserves output omitted from bounded memory."""
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 40)
    mock_proc = _make_mock_process(stdout_lines=[f"line-{i:04d}\n" for i in range(500)])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    res = await run_shell_command("emit", shell="node")

    assert "line-0499" in res, "the tail must reach the model"
    assert "line-0000" not in res, "the head must not be retained in memory"
    dump_path = res.split("saved to ")[1].split(" ")[0]
    dumped = open(dump_path, encoding="utf-8").read()
    assert "line-0000" in dumped and "line-0499" in dumped


@pytest.mark.asyncio
async def test_console_echo_stops_at_the_display_cap(monkeypatch):
    """Console echo is capped independently from captured output."""
    printed: list[str] = []
    monkeypatch.setattr(CFG, "LLM_MAX_CONSOLE_OUTPUT_CHARS", 100)
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 100000)
    # The echo moved to `stream_capture` with the class that does it; patching
    # `shell_mod` here would silently stop spying anything.
    monkeypatch.setattr(
        capture_mod, "zrb_print", lambda text, **kwargs: printed.append(text)
    )
    mock_proc = _make_mock_process(stdout_lines=[f"row-{i:04d}\n" for i in range(300)])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    res = await run_shell_command("emit", shell="node")
    console = "".join(printed)

    assert "console output capped" in console
    assert "row-0299" not in console, "echo stopped at the cap"
    assert "row-0299" in res, "capture is unaffected by the display cap"


@pytest.mark.asyncio
async def test_shell_output_collapses_on_a_ui_that_supports_it(monkeypatch):
    """The live echo grows and finishes into a collapsible block on a UI
    that implements the hooks — mirrors `_notify`'s `get_current_ui()`
    contract."""
    mock_ui = MagicMock()
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: mock_ui)
    mock_proc = _make_mock_process(stdout_lines=["hello\n", "world\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    await run_shell_command("emit", shell="node")

    # update_shell_output is throttled (see _LIVE_UPDATE_INTERVAL), so how
    # many intermediate calls land is timing-dependent — only the final
    # `finish_shell_output` call is guaranteed to hold the complete text.
    mock_ui.update_shell_output.assert_called()
    mock_ui.finish_shell_output.assert_called_once()
    key, collapsed, full = mock_ui.finish_shell_output.call_args[0]
    assert key == mock_ui.update_shell_output.call_args_list[0][0][0]
    assert "hello" in full
    assert "world" in full
    assert "Output" in collapsed


@pytest.mark.asyncio
async def test_shell_output_collapse_is_a_noop_with_no_current_ui(monkeypatch):
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: None)
    mock_proc = _make_mock_process(stdout_lines=["hello\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    res = await run_shell_command("emit", shell="node")  # must not raise

    assert "hello" in res


@pytest.mark.asyncio
async def test_shell_output_collapse_is_a_noop_without_the_hooks(monkeypatch):
    """UIs without collapse hooks remain unaffected."""
    mock_ui = MagicMock(spec=[])  # no attributes at all
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: mock_ui)
    mock_proc = _make_mock_process(stdout_lines=["hello\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    res = await run_shell_command("emit", shell="node")

    assert "hello" in res
