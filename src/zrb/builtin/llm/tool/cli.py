import subprocess


def run_shell_command(command: str) -> str:
    """Running an actual shell command on user's computer."""
    output = subprocess.check_output(
        command, shell=True, stderr=subprocess.STDOUT, text=True
    )
    return output
