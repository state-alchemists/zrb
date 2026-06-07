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
    max_chars: int | None = None,
) -> str:
    """
    Executes a non-interactive shell command under bash. Streams stdout/stderr
    live and returns truncated output.
    """
    return await _shell_cmd(
        command=command,
        cwd=cwd,
        timeout=timeout,
        preserved_head_lines=preserved_head_lines,
        preserved_tail_lines=preserved_tail_lines,
        max_chars=max_chars,
        shell="bash",
    )


run_bash_command.__name__ = "Bash"
