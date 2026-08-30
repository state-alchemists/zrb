import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.sandbox.os_sandbox import SandboxUnavailableError
from zrb.llm.tool import shell as shell_mod
from zrb.llm.tool import stream_capture as capture_mod
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


class _InterleavingStreamReader:
    """Like `_MockStreamReader`, but yields control between lines so two
    concurrent `run_shell_command()` calls genuinely interleave — matching
    real concurrent subprocess execution (confirmed: pydantic-ai runs
    same-turn tool calls as concurrent asyncio tasks)."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines
        self._pos = 0

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if self._pos < len(self._lines):
            line = self._lines[self._pos]
            self._pos += 1
            return line
        return b""


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


# The PID-tracking wrapper used to splice itself onto the command with `; }`,
# which corrupted any command whose LAST LINE cannot absorb a trailing `; }`.
# Every shape below failed with an opaque shell parse error pointing at a line
# number in a string the model never wrote, and models write all of them
# routinely. Real shells, not mocks: the bug was in generated shell syntax, so
# only an actual parse can catch a regression.
@pytest.mark.parametrize("shell", ["bash", "sh", ""])
@pytest.mark.parametrize(
    "command, expected",
    [
        # A heredoc: `EOF ; }` stops being a delimiter alone on its line, so the
        # shell swallowed the rest of the wrapper hunting for one.
        ("python3 - <<'EOF'\nprint('heredoc-ok')\nEOF", "heredoc-ok"),
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
    """The wrapper must report the command's status, not its own."""
    res = await run_shell_command("exit 7")
    assert "Exit Code: 7" in res


@pytest.mark.asyncio
async def test_empty_command_is_a_no_op_not_a_syntax_error():
    """`{ }` with no body is itself a syntax error, so an empty command must
    skip the wrapper rather than be turned into a shell failure."""
    res = await run_shell_command("   ")
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
    """A large timeout is the wrong tool for a server; background=True is.

    Checked against the `background` parameter's own schema description; see
    the note on `test_timeout_docstring_states_seconds_not_milliseconds`.
    """
    from pydantic_ai import Tool

    desc = Tool(run_shell_command).function_schema.json_schema["properties"][
        "background"
    ]["description"]

    assert "long-running" in desc
    assert "server" in desc


def test_docstring_points_unbounded_output_at_a_summarizing_form():
    """The output hazard needs naming next to the interactive-hang hazard.

    Three benchmarked trials ran an unscoped `git diff` in a dirty repo, each
    producing ~139MB and timing out. The docstring covered stdin hangs but said
    nothing about commands whose output has no ceiling.
    """
    doc = run_shell_command.__doc__ or ""

    assert "--stat" in doc
    assert "timeout" in doc


@pytest.mark.asyncio
async def test_full_output_survives_bounded_memory_retention(monkeypatch):
    """The head must stay recoverable even though it is never held in RAM.

    Retention is tail-biased and bounded, so the dump file is the only place
    the head still exists. If spilling regressed, this is where it shows.
    """
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
    """Echoing is per line and costs a regex plus a print; it needs a ceiling.

    Spies on the module's own printer rather than capturing a stream: zrb_print
    resolves its sink at call time, so fd-level capture does not see it.
    """
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
    """A UI that doesn't implement the collapse hooks (std_ui, Telegram,
    SSE, ...) must be unaffected — the command still runs and returns
    normally."""
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


@pytest.mark.asyncio
async def test_shell_output_collapse_swallows_a_broken_uis_exception(monkeypatch):
    """A UI whose hooks raise must never break the actual command — same
    contract as `_notify`'s broken-UI test."""
    mock_ui = MagicMock()
    mock_ui.update_shell_output.side_effect = RuntimeError("ui exploded")
    mock_ui.finish_shell_output.side_effect = RuntimeError("ui exploded")
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: mock_ui)
    mock_proc = _make_mock_process(stdout_lines=["hello\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    res = await run_shell_command("emit", shell="node")  # must not raise

    assert "hello" in res


@pytest.mark.asyncio
async def test_two_parallel_shell_calls_each_get_their_own_collapsible_block(
    monkeypatch,
):
    """The actual bug reported: two Shell commands running in parallel had
    their genuinely-interleaved live output collapse into ONE combined
    block, silently swallowing one command's lines. Runs two REAL
    `run_shell_command()` calls concurrently through a real `BufferedUI` —
    not mocks — so this fails the same way the live TUI did if the
    per-command isolation regresses.
    """
    # lazy: only this test needs a real UI implementation
    from zrb.llm.ui.buffered_ui import BufferedUI

    ui = BufferedUI(MagicMock())
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: ui)

    def _interleaving_process(lines: list[str]) -> MagicMock:
        proc = MagicMock()
        proc.stdout = _InterleavingStreamReader([line.encode() for line in lines])
        proc.stderr = _InterleavingStreamReader([])
        proc.wait = AsyncMock(return_value=0)
        proc.returncode = 0
        proc.pid = 12345
        return proc

    dog_lines = [f"dog {i}\n" for i in range(1, 6)]
    cat_lines = [f"cat {i}\n" for i in range(1, 6)]
    calls = iter([_interleaving_process(dog_lines), _interleaving_process(cat_lines)])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=lambda *a, **kw: next(calls)),
    )

    await asyncio.gather(
        run_shell_command("dog-loop", shell="bash"),
        run_shell_command("cat-loop", shell="bash"),
    )

    assert len(ui.rendered_blocks) == 2, "each command must get its own block"
    fulls = {block[2].full for block in ui.rendered_blocks}
    assert any(
        all(f"dog {i}" in f for i in range(1, 6)) for f in fulls
    ), "dog's own lines must all be in ONE of the two blocks"
    assert any(
        all(f"cat {i}" in f for i in range(1, 6)) for f in fulls
    ), "cat's own lines must all be in the OTHER block, not swallowed by dog's"


@pytest.mark.asyncio
async def test_timeout_after_flooding_is_not_diagnosed_as_a_hang(monkeypatch):
    """A command killed mid-write was not waiting on stdin.

    The old suggestion sent the model to `ps aux | grep` for a process that was
    already dead, and never named the actual remedy — bounding the output.
    """
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 50)

    async def _never_finishes(*args, **kwargs):
        await asyncio.sleep(10)

    mock_proc = _make_mock_process(stdout_lines=[f"x-{i:05d}\n" for i in range(400)])
    mock_proc.wait = _never_finishes
    mock_proc.returncode = None
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )
    monkeypatch.setattr(shell_mod, "terminate_process", AsyncMock())

    res = await run_shell_command("emit", shell="node", timeout=1)

    assert "(timed out)" in res
    assert "still writing, not waiting on input" in res
    assert "--stat" in res
    assert "ps aux" not in res


@pytest.mark.asyncio
async def test_timeout_without_output_still_reads_as_a_possible_hang(monkeypatch):
    """The quiet timeout keeps the original diagnosis — nothing was produced."""
    monkeypatch.setattr(shell_mod, "terminate_process", AsyncMock())

    res = await run_shell_command("sleep 5", timeout=1)

    assert "(timed out)" in res
    assert "ps aux" in res
    assert "still writing" not in res


def test_docstring_routes_file_work_to_the_file_tools():
    """Shell must say it is for running things, not for touching files.

    A model that reaches for `cat`/`sed -i`/`rm` gets none of what the file tools
    carry — post-write diagnostics, path validation, per-path auto-approval — so
    the routing rule belongs next to the schema it competes with, not only in the
    prompt where it applies to no tool in particular. It must also say to call
    Shell rather than Bash — Bash is no longer a tool, so the docstring is the
    only place the model learns that sub-agents listing `Bash` map to Shell.
    """
    doc = run_shell_command.__doc__ or ""

    for file_tool in ("Read", "Write", "Edit", "Grep", "Glob", "LS", "RM", "MV"):
        assert file_tool in doc
    for wrong in ("cat", "find", "sed -i"):
        assert wrong in doc

    assert "not Bash" in doc
