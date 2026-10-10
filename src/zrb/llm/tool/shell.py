import asyncio
import os
import platform
import tempfile
import time
from typing import Annotated, Any, Callable

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.agent_state import get_current_ui
from zrb.llm.sandbox import get_effective_sandbox_policy
from zrb.llm.sandbox.os_sandbox import (
    SandboxUnavailableError,
    format_sandbox_denied_message,
)
from zrb.llm.tool.stream_capture import StreamCapture
from zrb.util.cli.ansi import strip_ansi
from zrb.util.cmd.command import (
    close_transport,
    resolve_shell,
    terminate_process,
    wait_for_exit_and_drain,
)

# Minimum seconds between live shell-output repaints.
_LIVE_UPDATE_INTERVAL = 0.5


async def run_shell_command(
    command: Annotated[
        str, Field(description="The non-interactive command to execute.")
    ],
    cwd: Annotated[
        str,
        Field(
            description="Working directory; defaults to the current directory when empty."
        ),
    ] = "",
    timeout: Annotated[
        int, Field(description="Timeout in SECONDS, not milliseconds (default 120).")
    ] = 120,
    max_chars: Annotated[
        int,
        Field(
            description="Output character limit; -1 (default) uses the configured output limit."
        ),
    ] = -1,
    shell: Annotated[
        str,
        Field(
            description=(
                "bash/zsh/sh (POSIX), pwsh/cmd (Windows), node/ruby/php "
                "(runtime); empty uses the user's default shell."
            )
        ),
    ] = "",
    dangerously_skip_sandbox: Annotated[
        bool,
        Field(description="True exits the OS sandbox and requires user approval."),
    ] = False,
    background: Annotated[
        bool,
        Field(
            description=(
                "True for long-running processes (server, watcher, tail -f) — "
                "returns immediately with a handle; check status with MonitorProcess."
            )
        ),
    ] = False,
    description: Annotated[
        str,
        Field(
            description=(
                "Short label for the background process, shown by MonitorProcess; "
                "defaults to the command itself. Only meaningful with background=True."
            )
        ),
    ] = "",
) -> str:
    """
    Executes a non-interactive command in a shell. Returns truncated stdout/stderr.

    Use this to RUN things — builds, tests, linters, git, package managers,
    scripts. Not to touch files: Read/Write/Edit for contents, Grep/Glob/LS to
    search and list, RM/MV to remove and move. ``cat``, ``find``, ``sed -i`` and
    shell redirects are the wrong tool — the file tools carry diagnostics
    and path validation a shell command bypasses.

    Shell is zrb's only shell tool — call Shell, not Bash. A sub-agent or skill
    that asks for ``Bash`` is mapped to Shell; pass ``shell="bash"`` for bash.

    stdin is closed — pass ``-y``, ``--yes``, or ``CI=true`` for prompts.
    Output is truncated from the TOP (keeping the tail); full output is saved
    to a temp file whose path is reported — Grep/Read it.

    Prefer the bounded form: ``git diff --stat`` before ``git diff``,
    ``--name-only`` before full contents, ``head``/``wc -l`` before a raw dump.
    An unscoped command can emit hundreds of megabytes and be killed by its own
    timeout.
    """
    if background:
        return await _start_background_shell(
            command, cwd, description, shell, dangerously_skip_sandbox
        )
    if max_chars < 0:
        max_chars = CFG.LLM_MAX_OUTPUT_CHARS
    cwd = cwd or os.getcwd()
    resolved_shell, shell_flag = resolve_shell(shell)
    # Background-PID discovery needs POSIX process groups + pgrep/ps.
    use_pid_tracking = platform.system() != "Windows" and shell_flag == "-c"

    wrapper_command, temp_pid_file = _prepare_command(command, use_pid_tracking)

    try:
        argv, sandbox_note = _build_sandboxed_shell_argv(
            resolved_shell,
            shell_flag,
            wrapper_command,
            dangerously_skip_sandbox,
        )
    except SandboxUnavailableError as e:
        _cleanup_temp_file(temp_pid_file)
        return (
            f"Command refused by sandbox policy: {e}. "
            "[SYSTEM SUGGESTION]: this deployment requires OS-level sandboxing "
            f"for shell commands ({CFG.ENV_PREFIX}_LLM_SANDBOX_FALLBACK=deny). Use the in-process "
            "file tools instead, or ask the user to adjust the sandbox "
            "configuration."
        )

    process = None
    try:
        process = await start_process(argv, cwd)
        assert process.stdout is not None and process.stderr is not None

        ui = get_current_ui()
        supports_live_collapse = _supports_live_collapse(ui)
        stdout_cap, stderr_cap = _build_stream_captures(
            max_chars, supports_live_collapse
        )
        output_key = f"shell-{id(stdout_cap)}"
        on_chunk = (
            _make_live_shell_output_pusher(ui, output_key, stdout_cap, stderr_cap)
            if supports_live_collapse
            else None
        )

        timed_out = False
        drain_notices: list[str] = []
        try:
            try:
                # No return_exceptions: a broken reader should abort immediately.
                readers = asyncio.gather(
                    _read_stream(process.stdout, stdout_cap, on_chunk),
                    _read_stream(process.stderr, stderr_cap, on_chunk),
                )
                async with asyncio.timeout(timeout):
                    await wait_for_exit_and_drain(
                        process, readers, reporter=drain_notices.append
                    )
            except asyncio.TimeoutError:
                timed_out = True
                await terminate_process(
                    process,
                    CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
                    print_method=CFG.LOGGER.warning,
                )
        finally:
            if supports_live_collapse:
                _finish_shell_output(ui, output_key, stdout_cap, stderr_cap)

        bg_pids = _collect_background_pids(temp_pid_file, process.pid)

        result = _format_output(
            command,
            cwd,
            stdout_cap,
            stderr_cap,
            process.returncode,
            bg_pids,
            timed_out,
            timeout,
            drain_notices[0] if drain_notices else None,
        )
        if sandbox_note:
            result = f"{sandbox_note}\n{result}"
        return result

    except asyncio.CancelledError:
        # Kill + reap while the loop is alive, else the orphan logs "Loop ...
        # that handles pid N is closed" on exit. BaseException: a re-cancel
        # landing on the reap must not skip the kill.
        _cleanup_temp_file(temp_pid_file)
        try:
            await _kill_if_still_running(process)
        except BaseException:
            CFG.LOGGER.debug("Shell cleanup on cancel failed", exc_info=True)
        raise
    except Exception as e:
        _cleanup_temp_file(temp_pid_file)
        await _kill_if_still_running(process)
        return (
            f"Error executing command: {e}. "
            "[SYSTEM SUGGESTION]: Check the command syntax and that any "
            "referenced files or programs exist, then retry."
        )
    finally:
        _close_transport_if_started(process)


async def _start_background_shell(
    command: str,
    cwd: str,
    description: str,
    shell: str,
    dangerously_skip_sandbox: bool,
) -> str:
    """Hand the command to the background registry and report its handle."""
    # lazy: zrb internal — keeps the background registry off the hot
    # path most Shell calls take (foreground, non-backgrounded).
    from zrb.llm.tool.shell_background import get_shell_background_registry

    try:
        handle = await get_shell_background_registry().start(
            command, cwd, description, shell, dangerously_skip_sandbox
        )
    except SandboxUnavailableError as e:
        return format_sandbox_denied_message(e)
    return (
        f"Started background process. Handle: {handle}. "
        "Call MonitorProcess with this handle to check status."
    )


def _supports_live_collapse(ui: Any) -> bool:
    """Whether `ui` can render the command's output as one collapsible line."""
    return (
        ui is not None
        and callable(getattr(ui, "update_shell_output", None))
        and callable(getattr(ui, "finish_shell_output", None))
    )


def _build_stream_captures(
    max_chars: int, supports_live_collapse: bool
) -> tuple[StreamCapture, StreamCapture]:
    """A stdout/stderr capture pair; no console echo when the UI shows a live line."""
    echo_cap = CFG.LLM_MAX_CONSOLE_OUTPUT_CHARS
    return (
        StreamCapture(max_chars, echo_cap, print_live=not supports_live_collapse),
        StreamCapture(max_chars, echo_cap, print_live=not supports_live_collapse),
    )


def _close_transport_if_started(process: "asyncio.subprocess.Process | None") -> None:
    """Close *process*'s pipes. A timeout cancels the drain before it does, and
    left open they warn at GC once the loop is gone."""
    if process is not None:
        close_transport(process)


async def _kill_if_still_running(process: "asyncio.subprocess.Process | None") -> None:
    """Terminate *process* if it's still running."""
    if process is not None and process.returncode is None:
        await terminate_process(
            process,
            CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            print_method=CFG.LOGGER.warning,
        )


def _combined_echo(stdout_cap: StreamCapture, stderr_cap: StreamCapture) -> str:
    """The command's echo so far, stdout then stderr as separate sections
    (their interleaving is not tracked)."""
    sections = []
    if stdout_cap.echoed_text:
        sections.append(stdout_cap.echoed_text)
    if stderr_cap.echoed_text:
        sections.append(f"[stderr]\n{stderr_cap.echoed_text}")
    return "\n".join(sections)


def _format_live_shell_output(text: str) -> str:
    """Two-space indent per line, with a leading newline."""
    return "\n  " + text.replace("\n", "\n  ")


def _make_live_shell_output_pusher(
    ui: Any, key: str, stdout_cap: StreamCapture, stderr_cap: StreamCapture
) -> "Callable[[], None]":
    """Build a callback pushing the combined echo to `key`'s live line,
    throttled to `_LIVE_UPDATE_INTERVAL` (each update is an O(buffer) splice).
    Skipped updates lose nothing: `_finish_shell_output` uses the full echo.
    UI errors are swallowed.
    """
    last_update = 0.0

    def _push() -> None:
        nonlocal last_update
        now = time.monotonic()
        if now - last_update < _LIVE_UPDATE_INTERVAL:
            return
        last_update = now
        try:
            ui.update_shell_output(
                key,
                _format_live_shell_output(_combined_echo(stdout_cap, stderr_cap)),
            )
        except Exception as e:  # noqa: BLE001
            CFG.LOGGER.debug(f"Live shell output push failed: {e}")

    return _push


def _finish_shell_output(
    ui: Any, key: str, stdout_cap: StreamCapture, stderr_cap: StreamCapture
) -> None:
    """Collapse `key`'s live line into a one-line, expandable summary.

    Runs on every exit path so an aborted command never leaves its echo open.
    """
    try:
        full = _combined_echo(stdout_cap, stderr_cap)
        if not full:
            return
        char_count = len(full.strip())
        collapsed = _format_live_shell_output(f"💻 Output ({char_count} chars)")
        ui.finish_shell_output(key, collapsed, _format_live_shell_output(full))
    except Exception as e:  # noqa: BLE001
        CFG.LOGGER.debug(f"Final shell output capture failed: {e}")


def _prepare_command(command: str, use_pid_tracking: bool) -> tuple[str, str | None]:
    """Wrap the command to capture background PIDs when on a POSIX shell.

    Every wrapper token gets its own line: a `;`-spliced wrapper breaks a
    command ending in a heredoc, a comment, a `;` or a newline.
    """
    # `{ }` is a syntax error, so an empty command is not wrapped.
    if not use_pid_tracking or not command.strip():
        return command, None

    fd, temp_pid_file = tempfile.mkstemp(prefix="zrb_pids_")
    os.close(fd)

    # `|| echo $$`: under macOS Seatbelt a sandboxed shell cannot exec the
    # setuid /bin/ps, but the shell is the group leader there, so $$ is the
    # PGID. $$ is written first so it can be excluded even when a wrapper
    # makes process.pid != $$.
    wrapper_command = (
        f"echo $$ > {temp_pid_file}\n"
        f"{{\n{command}\n}}\n"
        f"__code=$?\n"
        f"pgrep -g $(ps -o pgid= -p $$ 2>/dev/null || echo $$) "
        f">> {temp_pid_file} 2>/dev/null\n"
        f"exit $__code"
    )
    return wrapper_command, temp_pid_file


def _build_sandboxed_shell_argv(
    shell: str, shell_flag: str, command: str, skip: bool
) -> tuple[list[str], str | None]:
    """Wrap the shell invocation per the sandbox policy; return ``(argv, note)``.

    Raises ``SandboxUnavailableError`` in fallback="deny" mode.
    """
    # lazy: tests patch zrb.llm.sandbox.build_sandboxed_argv; hoisting bypasses the mock
    from zrb.llm.sandbox import build_sandboxed_argv

    policy = get_effective_sandbox_policy()
    return build_sandboxed_argv([shell, shell_flag, command], policy, skip=skip)


async def start_process(argv: list[str], cwd: str) -> asyncio.subprocess.Process:
    """Start a (possibly sandbox-wrapped) command with piped output."""
    # Its own session/process group (setsid; ignored on Windows) lets
    # `pgrep -g` and kill reach the whole tree, and survives the sandbox
    # wrappers, which exec in place. DEVNULL stdin fails a stdin read fast.
    return await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        cwd=cwd,
        start_new_session=True,
        # asyncio's default 64KB StreamReader limit makes readline() raise on a
        # single long line (minified JS, one-line JSON logs), losing all output.
        # ponytail: 8MB line ceiling; switch to chunked read() if ever exceeded.
        limit=8 * 1024 * 1024,
    )


async def _read_stream(
    stream: asyncio.StreamReader,
    capture: StreamCapture,
    on_chunk: "Callable[[], None] | None" = None,
) -> None:
    """Read a stream line by line into *capture*, calling `on_chunk` after each line."""
    if not stream:
        return
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode(errors="replace")
        if decoded:
            stripped = strip_ansi(decoded)
            capture.echo(stripped)
            capture.feed(stripped)
            if on_chunk is not None:
                on_chunk()


def _collect_background_pids(temp_pid_file: str | None, process_pid: int) -> list[int]:
    """Read background PIDs from the temp file and remove it.

    Excludes the first line (the shell's ``$$``) and ``process_pid``.
    """
    bg_pids = []
    if temp_pid_file and os.path.exists(temp_pid_file):
        try:
            with open(temp_pid_file, "r", encoding="utf-8") as f:
                pids = [int(ln.strip()) for ln in f if ln.strip().isdigit()]
            shell_pid = pids[0] if pids else -1
            for pid in pids[1:]:
                if pid not in (process_pid, shell_pid, os.getpid()):
                    bg_pids.append(pid)
            os.remove(temp_pid_file)
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to parse background PIDs: {e}")
    return bg_pids


def _cleanup_temp_file(temp_pid_file: str | None):
    """Safely removes the temp file if it exists."""
    if temp_pid_file and os.path.exists(temp_pid_file):
        try:
            os.remove(temp_pid_file)
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to remove temp PID file: {e}")


def _format_output(
    command: str,
    cwd: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
    returncode: int | None,
    bg_pids: list[int],
    timed_out: bool,
    timeout: int,
    drain_notice: str | None = None,
) -> str:
    """Formats the command execution result into a readable string."""
    exit_code_str = str(returncode) if returncode is not None else "(none)"
    stdout_str, stderr_str = stdout_cap.text, stderr_cap.text
    if timed_out:
        exit_code_str = "(timed out)"
        stderr_str += f"\nError: Command timed out after {timeout} seconds."

    flooded = stdout_cap.truncated or stderr_cap.truncated
    total_chars = stdout_cap.total_chars + stderr_cap.total_chars
    dump_path = None
    if flooded:
        dump_path = _dump_full_output(
            command, cwd, stdout_cap, stderr_cap, exit_code_str
        )
    if drain_notice:
        stderr_str += f"\n{drain_notice}"
    stdout_cap.discard()
    stderr_cap.discard()

    suggestion = _suggest_next_step(
        command, stdout_str, stderr_str, timed_out, timeout, flooded, total_chars
    )
    return _assemble_output(
        command,
        cwd,
        stdout_str,
        stderr_str,
        exit_code_str,
        bg_pids,
        dump_path,
        suggestion,
    )


def _assemble_output(
    command: str,
    cwd: str,
    stdout_str: str,
    stderr_str: str,
    exit_code_str: str,
    bg_pids: list[int],
    dump_path: str | None,
    suggestion: str,
) -> str:
    output_parts = [
        f"Command: {command}",
        f"Directory: {cwd}",
        f"Stdout:\n{stdout_str.strip() or '(empty)'}",
        f"Stderr:\n{stderr_str.strip() or '(empty)'}",
        f"Exit Code: {exit_code_str}",
        f"Background PIDs: {', '.join(map(str, bg_pids)) if bg_pids else '(none)'}",
    ]
    if dump_path:
        output_parts.append(
            f"\n[SYSTEM SUGGESTION]: Output truncated (kept the tail). Full "
            f"stdout/stderr saved to {dump_path} — Grep it to locate sections, "
            "then Read."
        )
    if suggestion:
        output_parts.append(f"\n{suggestion}")
    return "\n".join(output_parts)


def _timeout_suggestion(timeout: int, flooded: bool, total_chars: int) -> str:
    """Tell a hung process apart from one drowning in its own output."""
    if flooded:
        return (
            "[SYSTEM SUGGESTION]: The command timed out after "
            f"{timeout}s having already produced {total_chars} characters — it "
            "was still writing, not waiting on input. Do not re-run it "
            "unchanged. Re-run a bounded form: scope it to a path, add a "
            "summarizing flag (`git diff --stat`, `--name-only`, `-l`), pipe "
            "through `head`/`wc -l`, or redirect to a file and Grep that. If it "
            "is meant to keep running, use background=True instead."
        )
    return (
        "[SYSTEM SUGGESTION]: The command timed out and the tool terminated "
        "it — there is nothing left to kill. If it was meant to keep running "
        "(a server, watcher, or tail -f), re-run it with background=True and "
        "check it with MonitorProcess. If it was meant to finish, do not "
        "re-run it unchanged: 'ps aux | grep <name>' tells you whether "
        "anything survived the kill. If nothing did, it was genuinely too "
        "slow or blocked — scope the work to a path, add a summarizing "
        "flag, or pass a non-interactive flag like '-y' or 'CI=true' before "
        "retrying. Next time, prefer the bounded form up front."
    )


def _suggest_next_step(
    command: str,
    stdout_str: str,
    stderr_str: str,
    timed_out: bool,
    timeout: int,
    flooded: bool,
    total_chars: int,
) -> str:
    """Map a recognizable failure shape to the next action worth taking."""
    suggestion = ""
    combined_output = (stdout_str + stderr_str).lower()
    if timed_out:
        suggestion = _timeout_suggestion(timeout, flooded, total_chars)
    elif "lock" in combined_output and (
        "apt" in command or "brew" in command or "dpkg" in command
    ):
        suggestion = (
            "[SYSTEM SUGGESTION]: A package manager lock was detected. "
            "Another installation process might be running. "
            "Do NOT force kill it immediately. Wait a moment and check running processes."
        )
    elif "permission denied" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: Permission denied. Look for a user-level "
            "fix first: install to the user's prefix, use a non-privileged "
            "port or path, or check the file's owner and group. Reaching for "
            "sudo is a last resort, and only if it is actually available."
        )
    elif "address already in use" in combined_output or "eaddrinuse" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: A port is already in use. "
            "Find the holder with 'lsof -i :<port>' or 'ss -tlnp | grep <port>' "
            "before killing or choosing a different port."
        )
    elif "command not found" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: Command not found. "
            "Check that the tool is installed and on PATH. "
            "If using a virtualenv or nvm/pyenv, verify it is activated."
        )
    elif (
        "no module named" in combined_output or "modulenotfounderror" in combined_output
    ):
        suggestion = (
            "[SYSTEM SUGGESTION]: Python module not found. "
            "Verify the virtualenv is activated and run 'pip install <package>' if missing."
        )
    elif "econnrefused" in combined_output or "connection refused" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: Connection refused. "
            "The target service may not be running. "
            "Check with 'ps aux | grep <service>' or 'docker ps' before retrying."
        )
    return suggestion


def _dump_full_output(
    command: str,
    cwd: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
    exit_code_str: str,
) -> str | None:
    """Persist untruncated output to a temp file; return its path, or None on failure."""
    # ponytail: not auto-deleted; the OS reaps its temp dir. Add cleanup only if it bloats.
    try:
        fd, path = tempfile.mkstemp(prefix="zrb_shell_", suffix=".log")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(
                f"Command: {command}\nDirectory: {cwd}\nExit Code: {exit_code_str}\n\n"
            )
            f.write("=== STDOUT ===\n")
            stdout_cap.write_full(f)
            f.write("\n\n=== STDERR ===\n")
            stderr_cap.write_full(f)
            f.write("\n")
        return path
    except Exception:
        return None


run_shell_command.__name__ = "Shell"
