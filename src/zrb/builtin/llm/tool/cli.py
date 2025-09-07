import subprocess


def run_shell_command(command: str) -> str:
    """
    Executes a shell command on the user's local machine and returns the output.

    This tool is powerful and should be used for tasks that require interacting
    with the command line, such as running scripts, managing system processes,
    or using command-line tools.

    **Security Warning:** This tool executes commands with the same permissions
    as the user running the assistant. Before executing any command that could
    modify files or system state (e.g., `git`, `npm`, `pip`, `docker`), you
    MUST explain what the command does and ask the user for confirmation.

    Args:
        command (str): The exact shell command to execute.

    Returns:
        dict[str, Any]: A dictionary containing return code, standard output (stdout),
            and standard error (stderr) from the command.
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
