import asyncio
import os
import platform
import re
import tempfile

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.sandbox.os_sandbox import SandboxUnavailableError
from zrb.util.cli.style import stylize_muted
from zrb.util.cmd.command import resolve_shell, terminate_process
from zrb.util.truncate import truncate_text


async def run_shell_command(
    command: str,
    cwd: str = "",
    timeout: int = 120,
    max_chars: int = -1,
    shell: str = "",
    dangerously_skip_sandbox: bool = False,
    background: bool = False,
    description: str = "",
) -> str:
    """
    Executes a non-interactive command in a shell. Returns truncated stdout/stderr.
    stdin is closed — prompts hang until timeout; pass `-y`, `--yes`, or `CI=true`.
    Batch with `&&`; use `cwd` instead of `cd`. Timed-out processes may continue in background.
    When output exceeds the size cap it is truncated from the TOP (keeping the
    tail, where errors land); the full stdout/stderr is saved to a temp file
    whose path is reported — Grep/Read it for the elided content.

    shell: "bash"/"zsh"/"sh" (POSIX), "pwsh"/"cmd" (Windows), or "node"/"ruby"/"php"
    (runtime — command treated as source code); empty = user's default shell.
    background=True returns a handle for MonitorProcess (timeout not applied).
    dangerously_skip_sandbox=True exits the OS sandbox — requires explicit user approval.
    max_chars=-1 uses the configured output limit.
    """
    if background:
        # lazy: keep the background registry off the hot foreground path.
        from zrb.llm.tool.shell_background import get_shell_background_registry

        try:
            handle = await get_shell_background_registry().start(
                command, cwd, description, shell, dangerously_skip_sandbox
            )
        except SandboxUnavailableError as e:
            return (
                f"Command refused by sandbox policy: {e}. "
                "[SYSTEM SUGGESTION]: this deployment requires OS-level "
                "sandboxing for shell commands "
                f"({CFG.ENV_PREFIX}_LLM_SANDBOX_FALLBACK=deny)."
            )
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

    try:
        process = await _start_process(argv, cwd)
        # _start_process creates the subprocess with stdout/stderr=PIPE, so both
        # readers are always present here (the type is StreamReader | None).
        assert process.stdout is not None and process.stderr is not None

        stdout_lines = []
        stderr_lines = []

        timed_out = False
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(process.stdout, stdout_lines),
                    _read_stream(process.stderr, stderr_lines),
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

        stdout_str = "".join(stdout_lines)
        stderr_str = "".join(stderr_lines)
        bg_pids = _collect_background_pids(temp_pid_file, process.pid)

        result = _format_output(
            command,
            cwd,
            stdout_str,
            stderr_str,
            process.returncode,
            bg_pids,
            timed_out,
            timeout,
            max_chars,
        )
        if sandbox_note:
            result = f"{sandbox_note}\n{result}"
        return result

    except Exception as e:
        _cleanup_temp_file(temp_pid_file)
        return (
            f"Error executing command: {e}. "
            "[SYSTEM SUGGESTION]: Check the command syntax and that any "
            "referenced files or programs exist, then retry."
        )


def _prepare_command(command: str, use_pid_tracking: bool) -> tuple[str, str | None]:
    """Wrap the command to capture background PIDs when on a POSIX shell."""
    if not use_pid_tracking:
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
        f"echo $$ > {temp_pid_file}; "
        f"{{ {command} ; }}; __code=$?; "
        f"pgrep -g $(ps -o pgid= -p $$ 2>/dev/null || echo $$) "
        f">> {temp_pid_file} 2>/dev/null; "
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
    # lazy: leaf module; policy is re-resolved per call so ContextVar binding
    # and CFG overrides are honored.
    from zrb.llm.sandbox import build_sandboxed_argv, get_effective_sandbox_policy

    policy = get_effective_sandbox_policy()
    return build_sandboxed_argv(shell, shell_flag, command, cwd, policy, skip=skip)


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
    )


async def _read_stream(stream: asyncio.StreamReader, lines_list: list[str]):
    """Reads from a stream line by line, printing to console and appending to list."""
    if not stream:
        return
    ANSI_ESCAPE = re.compile(
        r"(?:\x1B\[[0-?]*[ -/]*[@-~])|"  # CSI (Control Sequence Introducer)
        r"(?:\x1B\][^\a\x1b]*[\a\x1b])|"  # OSC (Operating System Command)
        r"(?:\x1B[0-9=>])"  # Simple 2-byte (DECSC, DECRC, etc.)
    )
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode(errors="replace")
        if decoded:
            stripped = ANSI_ESCAPE.sub("", decoded)
            shown = stylize_muted(stripped)
            zrb_print(f"  {shown}", end="", plain=True)  # Stream to console
            lines_list.append(stripped)


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
        except Exception:
            pass
    return bg_pids


def _cleanup_temp_file(temp_pid_file: str | None):
    """Safely removes the temp file if it exists."""
    if temp_pid_file and os.path.exists(temp_pid_file):
        try:
            os.remove(temp_pid_file)
        except Exception:
            pass


def _format_output(
    command: str,
    cwd: str,
    stdout_str: str,
    stderr_str: str,
    returncode: int | None,
    bg_pids: list[int],
    timed_out: bool,
    timeout: int,
    max_chars: int,
) -> str:
    """Formats the command execution result into a readable string."""
    exit_code_str = str(returncode) if returncode is not None else "(none)"
    if timed_out:
        exit_code_str = "(timed out)"
        stderr_str += f"\nError: Command timed out after {timeout} seconds."

    full_stdout, full_stderr = stdout_str, stderr_str
    stdout_str, stdout_truncated = truncate_text(stdout_str, max_chars, keep="tail")
    stderr_str, stderr_truncated = truncate_text(stderr_str, max_chars, keep="tail")
    dump_path = None
    if stdout_truncated or stderr_truncated:
        dump_path = _dump_full_output(
            command, cwd, full_stdout, full_stderr, exit_code_str
        )

    # Analyze for suggestions
    suggestion = ""
    combined_output = (stdout_str + stderr_str).lower()
    if timed_out:
        suggestion = (
            "[SYSTEM SUGGESTION]: The command timed out. "
            "This often means the process is still running in the background. "
            "Use 'ps aux | grep <process_name>' to check its status "
            "before retrying or killing it. Next time ensure you use non-interactive flags like '-y' or 'CI=true'."
        )
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


def _dump_full_output(
    command: str, cwd: str, stdout_str: str, stderr_str: str, exit_code_str: str
) -> str | None:
    """Persist untruncated output so the elided head stays recoverable.

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
            f.write(f"=== STDOUT ===\n{stdout_str}\n\n=== STDERR ===\n{stderr_str}\n")
        return path
    except Exception:
        return None


run_shell_command.__name__ = "Shell"
