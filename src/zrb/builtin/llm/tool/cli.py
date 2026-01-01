import asyncio
import sys
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_faint
from zrb.util.cmd.command import run_command

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
        display: Combination of standard output and standard error, interlaced
    """

    return_code: int
    stdout: str
    stderr: str
    display: str


async def run_shell_command(
    ctx: AnyContext, command: str, timeout: int = 30
) -> ShellCommandResult:
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
        cmd_result, return_code = await run_command(
            [CFG.DEFAULT_SHELL, "-c", command],
            print_method=_create_faint_print(ctx),
            timeout=timeout,
        )
        return {
            "return_code": return_code,
            "stdout": cmd_result.output,
            "stderr": cmd_result.error,
            "display": cmd_result.display,
        }
    except asyncio.TimeoutError:
        return {
            "return_code": 124,
            "stdout": "",
            "stderr": f"Command timeout after {timeout} seconds",
            "display": f"Command timeout after {timeout} seconds",
        }


def _create_faint_print(ctx: AnyContext) -> Callable[..., None]:
    def print_faint(text: str):
        ctx.print(stylize_faint(f"  {text}"), plain=True)

    return print_faint
