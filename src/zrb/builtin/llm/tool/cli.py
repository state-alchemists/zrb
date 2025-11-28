import subprocess
import sys

if sys.version_info >= (3, 12):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class ShellCommandResult(TypedDict):
    """
    Result of shell command execution

    Attributes:
        return_code: The return code, 0 indicating no error
        stdout: Standard output
        stderr: Standard error
    """

    return_code: int
    stdout: str
    stderr: str


def run_shell_command(command: str) -> ShellCommandResult:
    """
    Executes a non-interactive shell command on the user's machine.

    CRITICAL: This tool runs with user-level permissions. Explain commands that modify
        the system (e.g., `git`, `pip`) and ask for confirmation.
    IMPORTANT: Long-running processes should be run in the background (e.g., `command &`).

    Example:
    run_shell_command(command='ls -l')

    Args:
        command (str): The exact shell command to be executed.

    Returns:
        dict: return_code, stdout, and stderr.
    """
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    return {
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
