import asyncio
import os
import platform
import re
import signal
import tempfile

from zrb.context.any_context import zrb_print
from zrb.util.cli.style import stylize_faint


async def run_shell_command(command: str, timeout: int = 30) -> str:
    """
    Executes a shell command on the host system and returns its combined stdout and stderr.
    This is a powerful tool for running builds, tests, or system utilities.

    **CRITICAL SAFETY:**
    - DO NOT run destructive commands (e.g., `rm -rf /`) without absolute certainty.
    - Prefer specialized tools (like `read_file` or `write_file`) for file operations.

    **USAGE GUIDELINES:**
    - Use non-interactive commands.
    - **AVOID complex Bash syntax** (like brace expansion `{1..5}`) as it may not work in all environments.
    - **PREFER Python one-liners** (`python -c "..."`) for loops or complex logic to ensure safety and compatibility.
    - If a command is expected to produce massive output, use `timeout` or pipe to a file.
    - The output is streamed to the console in real-time.
    - **Background Processes:** You can use `&` to run processes in the background. The tool will report the PIDs of any background processes spawned.

    **RETURNS:**
    - A string containing the Command, Directory, Exit Code, Stdout, Stderr, and Background PIDs.
    - Format:
      ```
      Command: <command>
      Directory: <cwd>
      Stdout:
      <output>
      Stderr:
      <error output>
      Exit Code: <int>
      Background PIDs: <list>
      ```

    Args:
        command (str): The full shell command to execute.
        timeout (int): Maximum wait time in seconds before terminating the process. Defaults to 30.
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
    # allowing us to use `pgrep -g` effectively to find all processes in this tool's execution scope.
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
            shown = ANSI_ESCAPE.sub("", decoded)
            shown = stylize_faint(shown)
            zrb_print(f"  {shown}", end="", plain=True)  # Stream to console
            lines_list.append(decoded)


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
) -> str:
    """Formats the command execution result into a readable string."""
    exit_code_str = str(returncode) if returncode is not None else "(none)"
    if timed_out:
        exit_code_str = "(timed out)"
        stderr_str += f"\nError: Command timed out after {timeout} seconds."

    output_parts = [
        f"Command: {command}",
        f"Directory: {cwd}",
        f"Stdout:\n{stdout_str.strip() or '(empty)'}",
        f"Stderr:\n{stderr_str.strip() or '(empty)'}",
        f"Exit Code: {exit_code_str}",
        f"Background PIDs: {', '.join(map(str, bg_pids)) if bg_pids else '(none)'}",
    ]

    return "\n".join(output_parts)
