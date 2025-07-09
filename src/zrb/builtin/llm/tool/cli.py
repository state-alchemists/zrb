import subprocess


def run_shell_command(command: str) -> str:
    """
    Executes a shell command on the user's local machine and returns the output.

    This tool is powerful and should be used for tasks that require interacting with the command line, such as running scripts, managing system processes, or using command-line tools.

    **Security Warning:** This tool executes commands with the same permissions as the user running the assistant. Before executing any command that could modify files or system state (e.g., `git`, `npm`, `pip`, `docker`), you MUST explain what the command does and ask the user for confirmation.

    Args:
        command (str): The exact shell command to execute.

    Returns:
        str: The combined standard output (stdout) and standard error (stderr) from the command. If the command fails, this will contain the error message.
    Raises:
        subprocess.CalledProcessError: If the command returns a non-zero exit code, indicating an error.
    """
    try:
        output = subprocess.check_output(
            command, shell=True, stderr=subprocess.STDOUT, text=True
        )
        return output
    except subprocess.CalledProcessError as e:
        # Include the error output in the exception message
        raise subprocess.CalledProcessError(
            e.returncode, e.cmd, e.output, e.stderr
        ) from None
