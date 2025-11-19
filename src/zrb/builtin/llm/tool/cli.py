import subprocess
from typing import Any


def run_shell_command(command: str) -> dict[str, Any]:
    """
    Executes a non interactive shell command on the user's local machine and returns the output.

    Powerful tool for interacting with command line, running scripts, managing processes, or using CLI tools.

    **Security Warning:** Executes commands with user permissions. Before executing commands that modify files or system state (e.g., `git`, `npm`, `pip`, `docker`), you MUST explain what the command does and ask for confirmation.

    **Note:** Run servers or long running processes as background processes (e.g., `python -m http.server &`).

    Args:
        command (str): The exact shell command to execute.

    Returns:
        dict[str, Any]: Dictionary containing return code, stdout, and stderr.
            Example: {"return_code": 0, "stdout": "ok", "stderr": ""}
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
