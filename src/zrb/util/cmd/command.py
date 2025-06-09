import asyncio
import os
import re
import signal
import sys
from collections import deque
from collections.abc import Callable

import psutil

from zrb.cmd.cmd_result import CmdResult


def check_unrecommended_commands(cmd_script: str) -> dict[str, str]:
    """
    Check a command script for the use of unrecommended or non-POSIX compliant commands.

    Args:
        cmd_script (str): The command script string to check.

    Returns:
        dict[str, str]: A dictionary where keys are the violating commands/patterns
            and values are the reasons they are unrecommended.
    """
    banned_commands = {
        "<(": "Process substitution isn't POSIX compliant and causes trouble",
        "column": "Command isn't included in Ubuntu packages and is not POSIX compliant",
        "echo": "echo isn't consistent across OS; use printf instead",
        "eval": "Avoid eval as it can accidentally execute arbitrary strings",
        "realpath": "Not available by default on OSX",
        "source": "Not POSIX compliant; use '.' instead",
        " test": "Use '[' instead for consistency",
        "which": "Command in not POSIX compliant, use command -v",
    }
    banned_commands_regex = {
        r"grep.* -y": "grep -y does not work on Alpine; use grep -i",
        r"grep.* -P": "grep -P is not valid on OSX",
        r"grep[^|]+--\w{2,}": "grep long commands do not work on Alpine",
        r'readlink.+-.*f.+["$]': "readlink -f behaves differently on OSX",
        r"sort.*-V": "sort -V is not supported everywhere",
        r"sort.*--sort-versions": "sort --sort-version is not supported everywhere",
        r"\bls ": "Avoid using ls; use shell globs or find instead",
    }
    violations = {}
    # Check banned commands
    for cmd, reason in banned_commands.items():
        if cmd in cmd_script:
            violations[cmd] = reason
    # Check banned regex patterns
    for pattern, reason in banned_commands_regex.items():
        if re.search(pattern, cmd_script):
            violations[pattern] = reason
    return violations


async def __read_stream(
    stream: asyncio.StreamReader,
    print_method: Callable[..., None],
    max_lines: int,
) -> str:
    """
    Reads from the stream using the robust `readline()` and correctly
    interprets carriage returns (`\r`) as distinct print events.
    """
    captured_lines = deque(maxlen=max_lines if max_lines > 0 else 0)
    while True:
        try:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
        except ValueError:
            # Safety valve for the memory limit.
            error_msg = "[ERROR] A single line of output was too long to process."
            print_method(error_msg)
            if max_lines > 0:
                captured_lines.append(error_msg)
            break
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        except Exception:
            break
        decoded_line = line_bytes.decode("utf-8", errors="replace")
        parts = decoded_line.replace("\r", "\n").splitlines()
        for part in parts:
            clean_part = part.rstrip()
            if clean_part:
                try:
                    print_method(clean_part, end="\r\n")
                except Exception:
                    print_method(clean_part)
                if max_lines > 0:
                    captured_lines.append(clean_part)
    return "\r\n".join(captured_lines)


async def run_command(
    cmd: list[str],
    cwd: str | None = None,
    env_map: dict[str, str] | None = None,
    print_method: Callable[..., None] | None = None,
    register_pid_method: Callable[[int], None] | None = None,
    max_output_line: int = 1000,
    max_error_line: int = 1000,
) -> tuple[CmdResult, int]:
    """
    Executes a command using the robust `readline` strategy with a memory
    limit, and correctly handles terminal control characters in the output.
    """
    actual_print_method = print_method if print_method is not None else print
    if cwd is None:
        cwd = os.getcwd()
    # While environment variables alone weren't the fix, they are still
    # good practice for encouraging simpler output from tools.
    child_env = (env_map or os.environ).copy()
    child_env["TERM"] = "xterm-256color"  # A capable but standard terminal
    child_env["NO_COLOR"] = "0"  # Explicitly allow color
    # The most critical part for safety: the memory limit on the buffer.
    LINE_BUFFER_LIMIT = 10 * 1024 * 1024  # 10 MiB
    cmd_process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=child_env,
        # start_new_session=True,
        # stdin=asyncio.subprocess.DEVNULL,
        stdin=sys.stdin if sys.stdin.isatty() else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=LINE_BUFFER_LIMIT,
    )
    if register_pid_method is not None:
        register_pid_method(cmd_process.pid)
    # Use the new, simple, and correct stream reader.
    stdout_task = asyncio.create_task(
        __read_stream(cmd_process.stdout, actual_print_method, max_output_line)
    )
    stderr_task = asyncio.create_task(
        __read_stream(cmd_process.stderr, actual_print_method, max_error_line)
    )
    try:
        return_code = await cmd_process.wait()
        stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
        return CmdResult(stdout, stderr), return_code
    except (KeyboardInterrupt, asyncio.CancelledError):
        actual_print_method(">>>> Terasa ctrl + c")  # << This doesn't trigger
        try:
            os.killpg(cmd_process.pid, signal.SIGINT)
            await asyncio.wait_for(cmd_process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            # If it doesn't terminate, kill it forcefully
            actual_print_method(
                f"Process {cmd_process.pid} did not terminate gracefully, killing."
            )
            kill_pid(cmd_process.pid, print_method=actual_print_method)
        except Exception:
            pass
        # Final cleanup
        stdout_task.cancel()
        stderr_task.cancel()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        raise


def kill_pid(pid: int, print_method: Callable[..., None] | None = None):
    """
    Kill a process and its children given the parent process ID.

    Args:
        pid (int): The process ID of the parent process.
        print_method (Callable[..., None] | None): A method to print status messages.
            Defaults to the built-in print function.
    """
    actual_print_method = print_method if print_method is not None else print
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            actual_print_method(f"Killing child process {child.pid}")
            child.kill()
        actual_print_method(f"Killing process {pid}")
        parent.kill()
    except psutil.NoSuchProcess:
        actual_print_method(f"Process with pid: {pid} already terminated")
