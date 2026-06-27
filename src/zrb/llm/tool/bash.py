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
    max_chars: int = -1,
    dangerously_skip_sandbox: bool = False,
    background: bool = False,
    description: str = "",
) -> str:
    """
    Like Shell but always runs under bash (git-bash on Windows). Use when a script
    or skill assumes bash; otherwise prefer Shell with the user's default shell.
    stdin is closed — prompts hang until timeout; pass `-y`, `--yes`, or `CI=true`.
    Batch with `&&`; use `cwd` instead of `cd`. Timed-out processes may continue in background.

    background=True returns a handle for MonitorProcess (timeout not applied).
    dangerously_skip_sandbox=True exits the OS sandbox — requires explicit user approval.
    max_chars=-1 uses the configured output limit.
    """
    return await _shell_cmd(
        command=command,
        cwd=cwd,
        timeout=timeout,
        max_chars=max_chars,
        shell="bash",
        dangerously_skip_sandbox=dangerously_skip_sandbox,
        background=background,
        description=description,
    )


run_bash_command.__name__ = "Bash"
