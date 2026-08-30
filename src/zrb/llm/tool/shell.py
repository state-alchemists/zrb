import asyncio
import os
import platform
import tempfile
import time
from typing import Annotated, Any, Callable

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.agent.run.runtime_state import get_current_ui
from zrb.llm.sandbox import get_effective_sandbox_policy
from zrb.llm.sandbox.os_sandbox import (
    SandboxUnavailableError,
    format_sandbox_denied_message,
)
from zrb.llm.tool.stream_capture import StreamCapture
from zrb.util.cli.ansi import strip_ansi
from zrb.util.cmd.command import resolve_shell, terminate_process

# Minimum seconds between live shell-output UI updates — mirrors
# stream_response.py's _PROGRESS_REPAINT_INTERVAL: a chatty command (e.g.
# `find /`) can emit thousands of lines/sec, and each update is an
# O(buffer size) string splice. The *final* collapse always uses the
# complete, unthrottled accumulator (StreamCapture.echoed_text), so no
# output is ever lost — only how often the live view repaints.
_LIVE_UPDATE_INTERVAL = 0.1


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
        # lazy: keep the background registry off the hot foreground path.
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
    if max_chars < 0:
        max_chars = CFG.LLM_MAX_OUTPUT_CHARS
    cwd = cwd or os.getcwd()
    resolved_shell, shell_flag = resolve_shell(shell)
    # Background-PID discovery relies on POSIX process groups + pgrep/ps, so it
    # only applies to a POSIX `-c` shell on a POSIX OS. Windows and language
    # runtimes (node/php/powershell) skip the wrapper.
    use_pid_tracking = platform.system() != "Windows" and shell_flag == "-c"

    wrapper_command, temp_pid_file = _prepare_command(command, use_pid_tracking)

    try:
        argv, sandbox_note = _build_sandboxed_shell_argv(
            resolved_shell,
            shell_flag,
            wrapper_command,
            cwd,
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
        process = await _start_process(argv, cwd)
        # _start_process creates the subprocess with stdout/stderr=PIPE, so both
        # readers are always present here (the type is StreamReader | None).
        assert process.stdout is not None and process.stderr is not None

        echo_cap = CFG.LLM_MAX_CONSOLE_OUTPUT_CHARS
        ui = get_current_ui()
        supports_live_collapse = (
            ui is not None
            and callable(getattr(ui, "update_shell_output", None))
            and callable(getattr(ui, "finish_shell_output", None))
        )
        # print_live=False when the UI has a better mechanism: StreamCapture
        # would otherwise show the same output twice (its own zrb_print
        # *and* the collapsible live line below).
        stdout_cap = StreamCapture(
            max_chars, echo_cap, print_live=not supports_live_collapse
        )
        stderr_cap = StreamCapture(
            max_chars, echo_cap, print_live=not supports_live_collapse
        )
        output_key = f"shell-{id(stdout_cap)}"
        on_chunk = (
            _make_live_shell_output_pusher(ui, output_key, stdout_cap, stderr_cap)
            if supports_live_collapse
            else None
        )

        timed_out = False
        try:
            try:
                # Fail-fast fan-out: a broken reader/wait should abort
                # immediately, not be masked by return_exceptions.
                await asyncio.wait_for(
                    asyncio.gather(
                        _read_stream(process.stdout, stdout_cap, on_chunk),
                        _read_stream(process.stderr, stderr_cap, on_chunk),
                        process.wait(),
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                timed_out = True
                await terminate_process(
                    process,
                    CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
                    print_method=CFG.LOGGER.warning,
                )
        finally:
            # Always attempt the collapse once echoing may have started —
            # including on cancellation or a stream error below — so a
            # failed/aborted command never leaves its raw echo stuck open
            # on screen. A no-op if nothing was ever echoed.
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
        )
        if sandbox_note:
            result = f"{sandbox_note}\n{result}"
        return result

    except asyncio.CancelledError:
        # Cancellation must not orphan the subprocess: ``asyncio.run`` closes
        # the loop right after the chat ends, and a child still alive then logs
        # "Loop <...> that handles pid N is closed" when it finally exits (its
        # exit event can no longer be delivered). Kill + reap while the loop is
        # still alive, then re-raise so cancellation propagates. BaseException,
        # not Exception: a re-cancel landing on the reap must not skip the kill.
        _cleanup_temp_file(temp_pid_file)
        try:
            await _kill_if_still_running(process)
        except BaseException:
            CFG.LOGGER.debug("Shell cleanup on cancel failed", exc_info=True)
        raise
    except Exception as e:
        _cleanup_temp_file(temp_pid_file)
        # A failure after the process started (e.g. a stream error) must not
        # leave the command running detached with no handle to it.
        await _kill_if_still_running(process)
        return (
            f"Error executing command: {e}. "
            "[SYSTEM SUGGESTION]: Check the command syntax and that any "
            "referenced files or programs exist, then retry."
        )


async def _kill_if_still_running(process: "asyncio.subprocess.Process | None") -> None:
    """Terminate *process* if it's still running (no-op otherwise).

    Shared by the cancellation and error paths of `run_shell_command` — a
    failure must not leave the command running detached with no handle to it.
    """
    if process is not None and process.returncode is None:
        await terminate_process(
            process,
            CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            print_method=CFG.LOGGER.warning,
        )


def _combined_echo(stdout_cap: StreamCapture, stderr_cap: StreamCapture) -> str:
    """The command's current combined echo, from each stream's own
    `echoed_text` accumulator — not re-read from the buffer (see
    `StreamCapture.echoed_text`), the same "don't trust the rendered
    screen" contract `StreamEventHandler` uses for thinking/text. Stdout
    and stderr are shown as separate sections since each only tracks its
    own chronological order, not the interleaving between the two as they
    actually printed.
    """
    sections = []
    if stdout_cap.echoed_text:
        sections.append(stdout_cap.echoed_text)
    if stderr_cap.echoed_text:
        sections.append(f"[stderr]\n{stderr_cap.echoed_text}")
    return "\n".join(sections)


def _format_live_shell_output(text: str) -> str:
    """Two-space indent per line, leading "\\n" for its own block
    boundary — matches the convention every other mid-turn writer outside
    `StreamEventHandler` follows (see `web.py`'s `_notify`)."""
    return "\n  " + text.replace("\n", "\n  ")


def _make_live_shell_output_pusher(
    ui: Any, key: str, stdout_cap: StreamCapture, stderr_cap: StreamCapture
) -> "Callable[[], None]":
    """Build a throttled callback that pushes the current combined
    stdout+stderr echo to `key`'s own live line via `ui.update_shell_output`.

    Called after every new line from either stream; skips updates closer
    together than `_LIVE_UPDATE_INTERVAL` (mirrors `stream_response.py`'s
    spinner throttle — a chatty command can emit thousands of lines/sec,
    and each update is an O(buffer size) string splice). Nothing is lost
    by skipping: `_finish_shell_output` always uses the complete,
    unthrottled accumulator. A missing/broken UI must never break the
    actual command — same contract as `web.py`'s `_notify`.
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
        except Exception:  # noqa: BLE001
            pass

    return _push


def _finish_shell_output(
    ui: Any, key: str, stdout_cap: StreamCapture, stderr_cap: StreamCapture
) -> None:
    """Collapse `key`'s live line (opened by
    `_make_live_shell_output_pusher`'s updates) into a one-line summary,
    Ctrl+O-expandable back to the full echo. Called unconditionally once
    echoing may have started — including on cancellation or a stream
    error — so a failed/aborted command never leaves its raw echo stuck
    open on screen. A no-op if nothing was ever echoed, or if the UI's
    hook raises.
    """
    try:
        full = _combined_echo(stdout_cap, stderr_cap)
        if not full:
            return
        char_count = len(full.strip())
        collapsed = _format_live_shell_output(f"🖥️ Output ({char_count} chars)")
        ui.finish_shell_output(key, collapsed, _format_live_shell_output(full))
    except Exception:  # noqa: BLE001
        pass


def _prepare_command(command: str, use_pid_tracking: bool) -> tuple[str, str | None]:
    """Wrap the command to capture background PIDs when on a POSIX shell.

    **Every wrapper token gets its own line.** Splicing the wrapper on with `;`
    separators — ``{ <command> ; }; __code=$?; …`` — corrupts any command whose
    *last line* cannot tolerate a trailing `; }`: a heredoc (the `EOF` delimiter
    stops being alone on its line, so the shell swallows the rest of the wrapper
    hunting for it), a trailing comment (`# …` eats the rest of the line), a
    trailing `;`, and — on bash/sh — a command merely ending in a newline.
    Models write all four constantly, and the failure surfaces as an opaque
    `parse error near '\\n'` pointing at a line number in a string the model
    never wrote. Newline separators make the command a statement of its own, so
    nothing the model writes can run into the wrapper.
    """
    # An empty command has no body to wrap: `{ }` is itself a syntax error, so
    # the wrapper would turn a harmless no-op into a shell failure.
    if not use_pid_tracking or not command.strip():
        return command, None

    fd, temp_pid_file = tempfile.mkstemp(prefix="zrb_pids_")
    os.close(fd)

    # Logic to capture background PIDs
    # We use `pgrep -g` to find processes in the current process group.
    # `$(ps -o pgid= -p $$)` gets the PGID of the shell executing the command;
    # `|| echo $$` covers macOS Seatbelt, where /bin/ps is setuid root and a
    # sandboxed shell cannot exec it — there the shell IS the group leader
    # (start_new_session=True + the sandbox wrappers exec in place), so $$ is
    # the PGID. The shell's own PID ($$) is written first so
    # _collect_background_pids can exclude it even when a wrapper makes
    # process.pid != $$.
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
    shell: str, shell_flag: str, command: str, cwd: str, skip: bool
) -> tuple[list[str], str | None]:
    """Wrap the shell invocation per the in-force sandbox policy.

    Returns ``(argv, note)``; with the sandbox disabled (the default) this is
    a passthrough. Raises ``SandboxUnavailableError`` in fallback="deny" mode.
    """
    # lazy: tests patch zrb.llm.sandbox.build_sandboxed_argv; hoisting would
    # bind the name at this module's load time and bypass the mock.
    from zrb.llm.sandbox import build_sandboxed_argv

    policy = get_effective_sandbox_policy()
    return build_sandboxed_argv([shell, shell_flag, command], cwd, policy, skip=skip)


async def _start_process(argv: list[str], cwd: str) -> asyncio.subprocess.Process:
    """Starts the subprocess with appropriate settings."""
    # start_new_session=True puts the shell in its own session/process group
    # (setsid on POSIX, ignored on Windows). This lets `pgrep -g` find spawned
    # processes and lets terminate/kill target the whole tree. The sandbox
    # wrappers (sandbox-exec/bwrap) exec the shell in place, so these
    # semantics survive wrapping.
    # stdin is DEVNULL so a command that reads stdin fails fast instead of
    # hanging until the timeout.
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
    """Reads from a stream line by line, echoing to console and capturing.

    `on_chunk`, when given, is called after every line (a UI-side live
    update — see `_make_live_shell_output_pusher`); `capture.echo` still
    runs regardless, for its own budget tracking and `echoed_text`
    accumulation (its `zrb_print` side effect is what `print_live=False`
    suppresses, when `on_chunk` is the one actually driving the display).
    """
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
    """Reads background PIDs from the temp file and cleans it up.

    The first line is the wrapper shell's own ``$$`` (see ``_prepare_command``)
    — excluded along with ``process_pid``, which can differ from ``$$`` when a
    sandbox wrapper sits between the spawned process and the shell.
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
    """Tell a hung process apart from one drowning in its own output.

    A command killed after emitting megabytes was not waiting on stdin — it was
    still writing. Sending that one off to ``ps aux | grep`` points the model at
    a process that is already dead and says nothing about the actual remedy,
    which is to bound the output. Both readings stay available because a slow
    build can be genuinely long-running *and* verbose.
    """
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
        "[SYSTEM SUGGESTION]: The command timed out. "
        "This often means the process is still running in the background. "
        "Use 'ps aux | grep <process_name>' to check its status "
        "before retrying or killing it. Next time ensure you use non-interactive flags like '-y' or 'CI=true'."
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
            "[SYSTEM SUGGESTION]: Permission denied. "
            "Consider if this command requires 'sudo' (if available) or check file permissions."
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
    """Persist untruncated output so the elided head stays recoverable.

    Streams each capture's spill file in rather than materializing it, so a
    multi-gigabyte command costs one file copy instead of one resident string.

    Best-effort: returns the temp-file path, or None if the write fails.
    Cross-platform — tempfile targets %TEMP% on Windows, $TMPDIR/tmp elsewhere.
    """
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
