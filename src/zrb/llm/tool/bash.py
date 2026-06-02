"""Bash tool — alias for Shell (Claude compatibility)."""

from zrb.llm.tool.shell import run_shell_command as _shell_cmd


async def run_shell_command(*args, **kwargs):
    return await _shell_cmd(*args, **kwargs)


run_shell_command.__name__ = "Bash"
