import asyncio
import os
import re
import sys
from collections.abc import Callable

from zrb.cmd.cmd_result import CmdResult


def check_unrecommended_commands(cmd_script: str) -> dict[str, str]:
    banned_commands = {
        "<(": "Process substitution isn't POSIX compliant and causes trouble",
        "column": "Command isn't included in Ubuntu packages and is not POSIX compliant",
        "echo": "echo isn't consistent across OS; use printf instead",
        "eval": "Avoid eval as it can accidentally execute arbitrary strings",
        "realpath": "Not available by default on OSX",
        "source": "Not POSIX compliant; use '.' instead",
        " test": "Use '[' instead for consistency",
        "which": "Command in not POSIX compliant, use command -v",
    }
    banned_commands_regex = {
        r"grep.* -y": "grep -y does not work on Alpine; use grep -i",
        r"grep.* -P": "grep -P is not valid on OSX",
        r"grep[^|]+--\w{2,}": "grep long commands do not work on Alpine",
        r'readlink.+-.*f.+["$]': "readlink -f behaves differently on OSX",
        r"sort.*-V": "sort -V is not supported everywhere",
        r"sort.*--sort-versions": "sort --sort-version is not supported everywhere",
        r"\bls ": "Avoid using ls; use shell globs or find instead",
    }
    violations = {}
    # Check banned commands
    for cmd, reason in banned_commands.items():
        if cmd in cmd_script:
            violations[cmd] = reason
    # Check banned regex patterns
    for pattern, reason in banned_commands_regex.items():
        if re.search(pattern, cmd_script):
            violations[pattern] = reason
    return violations


async def run_command(
    cmd: list[str],
    cwd: str | None = None,
    env_map: dict[str, str] | None = None,
    log_method: Callable[..., None] = print,
    max_output_line: int = 1000,
    max_error_line: int = 1000,
) -> tuple[CmdResult, int]:
    async def __read_stream(
        stream, log_method: Callable[..., None], max_lines: int
    ) -> str:
        lines = []
        while True:
            line = await stream.readline()
            if not line:
                break
            line = line.decode("utf-8").rstrip()
            lines.append(line)
            if len(lines) > max_lines:
                lines.pop(0)  # Keep only the last max_lines
            log_method(line)
        return "\n".join(lines)

    cmd_process = None
    try:
        if cwd is None:
            cwd = os.getcwd()
        if env_map is None:
            env_map = os.environ
        cmd_process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdin=sys.stdin if sys.stdin.isatty() else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env_map,
            bufsize=0,
        )
        stdout_task = asyncio.create_task(
            __read_stream(cmd_process.stdout, log_method, max_output_line)
        )
        stderr_task = asyncio.create_task(
            __read_stream(cmd_process.stderr, log_method, max_error_line)
        )
        # Wait for process to complete and gather stdout/stderr
        return_code = await cmd_process.wait()
        stdout = await stdout_task
        stderr = await stderr_task
        return CmdResult(stdout, stderr), return_code
    finally:
        if cmd_process is not None and cmd_process.returncode is None:
            cmd_process.terminate()
