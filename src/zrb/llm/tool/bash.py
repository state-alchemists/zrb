"""Bash tool — runs commands under bash (Claude compatibility).

Distinct from ``Shell`` (which uses the default shell): ``Bash`` always
executes under ``bash``, matching Claude Code's Bash tool semantics (git-bash
on Windows). Many Claude skills assume a ``Bash`` tool by name.
"""

from zrb.llm.tool.shell import run_shell_command as _shell_cmd


async def run_bash_command(
    command: str,
    cwd: str = "",
    timeout: int = 120,
    preserved_head_lines: int = 500,
    preserved_tail_lines: int = 500,
    max_chars: int = 0,
    dangerously_skip_sandbox: bool = False,
    background: bool = False,
    description: str = "",
) -> str:
    """
    Executes a non-interactive command under bash (git-bash on Windows).
    Streams stdout/stderr live and returns truncated output.

    Commands must be fully non-interactive: pass `-y`, `--yes`, `CI=true`, or
    equivalent auto-confirmation flags so the process never waits for stdin —
    stdin is closed, and interactive prompts hang until the timeout.

    Batch independent commands with `&&` to avoid extra round-trips
    (e.g. `pytest && flake8 src`). Use the `cwd` parameter instead of
    `cd <dir> && ...` to set the working directory.

    Default `timeout` is 120 seconds; timed-out processes may continue in the
    background.

    Args:
        dangerously_skip_sandbox: Run this command OUTSIDE the OS-level sandbox
            (when one is active). Only set it when a command genuinely needs to
            write outside the workspace; it always requires explicit user
            approval.
        background: Start the command in the BACKGROUND and return a handle
            immediately instead of blocking (long-running processes). Poll, wait,
            or kill it with MonitorProcess(handle); `timeout` is not applied.
        description: Optional human-readable label for a background process.
    """
    return await _shell_cmd(
        command=command,
        cwd=cwd,
        timeout=timeout,
        preserved_head_lines=preserved_head_lines,
        preserved_tail_lines=preserved_tail_lines,
        max_chars=max_chars,
        shell="bash",
        dangerously_skip_sandbox=dangerously_skip_sandbox,
        background=background,
        description=description,
    )


run_bash_command.__name__ = "Bash"
