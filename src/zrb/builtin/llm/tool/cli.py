import subprocess


def run_shell_command(command: str) -> str:
    """Execute a shell command and return its combined stdout and stderr.
    Args:
        command (str): Shell command to execute on the user's system.
    Returns:
        str: The command's output (stdout and stderr combined).
    Raises:
        subprocess.CalledProcessError: If the command returns a non-zero exit code.
        subprocess.SubprocessError: If there's an issue with subprocess execution.
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
