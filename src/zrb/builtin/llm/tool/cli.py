import subprocess


def run_shell_command(command: str) -> str:
    """Running a shell command"""
    output = subprocess.check_output(
        command, shell=True, stderr=subprocess.STDOUT, text=True
    )
    return output
