import shlex
import subprocess
from typing import Optional


def run_shell_command(command: str, timeout: Optional[int] = 60) -> str:
    """
    Execute a shell command safely with proper error handling.
    
    Args:
        command: The command to execute
        timeout: Maximum execution time in seconds (default: 60)
        
    Returns:
        The command output (stdout and stderr combined)
        
    Raises:
        ValueError: If command is empty
        subprocess.TimeoutExpired: If command execution exceeds timeout
        subprocess.CalledProcessError: If command returns non-zero exit code
    """
    if not command or command.strip() == "":
        raise ValueError("Command cannot be empty")
    
    try:
        # Use list form with args to avoid shell injection vulnerabilities
        # Only use shell=True when shell features like pipes are needed
        if any(char in command for char in '|&;()<>{}[]$\\"\'`'):
            # Command contains shell metacharacters, use shell=True but with caution
            output = subprocess.check_output(
                command,
                shell=True,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout
            )
        else:
            # Simple command without shell metacharacters, safer execution
            args = shlex.split(command)
            output = subprocess.check_output(
                args,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout
            )
        return output
    except subprocess.TimeoutExpired:
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=timeout,
            output="Command execution timed out"
        )
    except subprocess.CalledProcessError as e:
        # Include the error output in the exception
        error_message = f"Command failed with exit code {e.returncode}"
        if e.output:
            error_message += f"\nOutput: {e.output}"
        e.output = error_message
        raise e
    except Exception as e:
        # Catch other exceptions for better error messages
        raise RuntimeError(f"Error executing command: {str(e)}")
