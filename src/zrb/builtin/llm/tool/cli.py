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


def run_shell_command(command: str, timeout: int = 30) -> ShellCommandResult:
    """
    Executes a non-interactive shell command on the user's machine.

    **EFFICIENCY TIP:**
    Combine multiple shell commands into a single call using `&&` or `;` to save steps.
    Example: `mkdir new_dir && cd new_dir && touch file.txt`

    CRITICAL: This tool runs with user-level permissions. Explain commands that modify
        the system (e.g., `git`, `pip`) and ask for confirmation.
    IMPORTANT: Long-running processes should be run in the background (e.g., `command &`).

    Example:
    run_shell_command(command='ls -l', timeout=30)

    Args:
        command (str): The exact shell command to be executed.
        timeout (int): The maximum time in seconds to wait for the command to finish.
            Defaults to 30.

    Returns:
        dict: return_code, stdout, and stderr.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "return_code": int(result.returncode),
            "stdout": str(result.stdout or ""),
            "stderr": str(result.stderr or ""),
        }
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return {
            "return_code": 124,
            "stdout": str(stdout),
            "stderr": f"{stderr}\nError: Command timed out after {timeout} seconds".strip(),
        }
