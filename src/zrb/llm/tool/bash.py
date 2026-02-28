import asyncio
import os
import platform
import re
import signal
import tempfile

from zrb.context.any_context import zrb_print
from zrb.util.cli.style import stylize_faint
from zrb.util.truncate import truncate_output


async def run_shell_command(
    command: str,
    timeout: int = 30,
    preserved_head_lines: int = 500,
    preserved_tail_lines: int = 500,
    max_chars: int = 100000,
) -> str:
    """
    Executes a non-interactive shell command.

    MANDATES:
    - NEVER use for reading/writing files; use file tools instead.
    - ALWAYS prefer non-interactive flags (e.g., `-y`, `--yes`, `--watch=false`, `CI=true`) for scaffolding tools or test runners to avoid persistent watch modes hanging the execution.
    - If timeout occurs, process likely runs in background; check `ps aux` before retrying.
    """
    cwd = os.getcwd()
    is_windows = platform.system() == "Windows"

    wrapper_command, temp_pid_file = _prepare_command(command, is_windows)

    try:
        process = await _start_process(wrapper_command, is_windows)

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
            await _terminate_process(process, is_windows)

        stdout_str = "".join(stdout_lines)
        stderr_str = "".join(stderr_lines)
        bg_pids = _collect_background_pids(temp_pid_file, process.pid)

        return _format_output(
            command,
            cwd,
            stdout_str,
            stderr_str,
            process.returncode,
            bg_pids,
            timed_out,
            timeout,
            preserved_head_lines,
            preserved_tail_lines,
            max_chars,
        )

    except Exception as e:
        _cleanup_temp_file(temp_pid_file)
        return f"Error executing command: {e}"


def _prepare_command(command: str, is_windows: bool) -> tuple[str, str | None]:
    """Prepares the command for execution, handling PID tracking on non-Windows systems."""
    if is_windows:
        return command, None

    fd, temp_pid_file = tempfile.mkstemp(prefix="zrb_pids_")
    os.close(fd)

    # Logic to capture background PIDs
    # We use `pgrep -g` to find processes in the current process group.
    # `$(ps -o pgid= -p $$)` gets the PGID of the shell executing the command.
    wrapper_command = (
        f"{{ {command} ; }}; __code=$?; "
        f"pgrep -g $(ps -o pgid= -p $$) > {temp_pid_file} 2>/dev/null; "
        f"exit $__code"
    )
    return wrapper_command, temp_pid_file


async def _start_process(command: str, is_windows: bool) -> asyncio.subprocess.Process:
    """Starts the subprocess with appropriate settings."""
    # start_new_session=True (via os.setsid) ensures the shell gets its own process group,
    # allowing us to use `pgrep -g` effectively to find all processes
    # in this tool's execution scope.
    return await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=os.setsid if not is_windows else None,
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
            shown = stylize_faint(stripped)
            zrb_print(f"  {shown}", end="", plain=True)  # Stream to console
            lines_list.append(stripped)


async def _terminate_process(process: asyncio.subprocess.Process, is_windows: bool):
    """Terminates the process and its process group if possible."""
    if process.returncode is not None:
        return

    try:
        # Kill the whole process group
        if not is_windows:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        await asyncio.wait_for(process.wait(), timeout=5)
    except (ProcessLookupError, asyncio.TimeoutError):
        if not is_windows:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                pass
        else:
            process.kill()


def _collect_background_pids(temp_pid_file: str | None, process_pid: int) -> list[int]:
    """Reads background PIDs from the temp file and cleans it up."""
    bg_pids = []
    if temp_pid_file and os.path.exists(temp_pid_file):
        try:
            with open(temp_pid_file, "r") as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line.isdigit():
                        pid = int(clean_line)
                        # Exclude the wrapper shell PID and our process PID
                        if pid != process_pid and pid != os.getpid():
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
    preserved_head_lines: int,
    preserved_tail_lines: int,
    max_chars: int,
) -> str:
    """Formats the command execution result into a readable string."""
    exit_code_str = str(returncode) if returncode is not None else "(none)"
    if timed_out:
        exit_code_str = "(timed out)"
        stderr_str += f"\nError: Command timed out after {timeout} seconds."

    stdout_str, _ = truncate_output(
        stdout_str, preserved_head_lines, preserved_tail_lines, 1000, max_chars
    )
    stderr_str, _ = truncate_output(
        stderr_str, preserved_head_lines, preserved_tail_lines, 1000, max_chars
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
            "Consider if this command requires user usage of 'sudo' "
            "(if available) or check file permissions."
        )
    output_parts = [
        f"Command: {command}",
        f"Directory: {cwd}",
        f"Stdout:\n{stdout_str.strip() or '(empty)'}",
        f"Stderr:\n{stderr_str.strip() or '(empty)'}",
        f"Exit Code: {exit_code_str}",
        f"Background PIDs: {', '.join(map(str, bg_pids)) if bg_pids else '(none)'}",
    ]
    if suggestion:
        output_parts.append(f"\n{suggestion}")
    return "\n".join(output_parts)


run_shell_command.__name__ = "Bash"
