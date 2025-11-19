import subprocess
from typing import Any


def run_shell_command(command: str) -> dict[str, Any]:
    """
    Execute a non-interactive shell command on the user's local machine.

    **Security Warning:** This tool executes commands with user-level permissions. Before using commands that modify the file system or system state (e.g., `git`, `npm`, `pip`, `docker`), you MUST explain the command and its potential impact, and then ask for user confirmation.

    This is a powerful tool for interacting with the command line, running scripts, and managing processes.

    **Note:** Long-running processes or servers should be run in the background (e.g., `python -m http.server &`).

    Args:
        command (str): The exact shell command to be executed.

    Returns:
        A dictionary containing the `return_code` (integer), `stdout` (string), and `stderr` (string) of the command execution.
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
