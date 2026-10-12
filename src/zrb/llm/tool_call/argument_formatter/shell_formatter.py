"""Approval body for `Shell`: the command, fenced for the shell that runs it."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from zrb.cmd.command import resolve_shell
from zrb.config.helper import get_shell_name
from zrb.llm.tool_call.argument_formatter.util import render_indented_markdown
from zrb.llm.tool_call.args import parse_tool_args

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput

# Fence language per shell, so pygments highlights the command as the shell
# that will run it. `bash` stands in for the POSIX shells it reads the same
# way; an unmapped shell keeps a plain fence rather than claiming a syntax it
# does not have.
_SHELL_FENCES = {
    "bash": "bash",
    "sh": "bash",
    "zsh": "bash",
    "ksh": "bash",
    "fish": "fish",
    "pwsh": "powershell",
    "powershell": "powershell",
    "cmd": "batch",
    "node": "javascript",
    "ruby": "ruby",
    "php": "php",
}

# `run_shell_command`'s defaults. A call that departs from one shows it:
# approval is the safety gate for the call, so a non-default cwd, a custom
# timeout or an unsandboxed run must not be invisible (ADR-0061, ADR-0062).
_DEFAULT_TIMEOUT = 120
_DEFAULT_MAX_CHARS = -1

# Markdown ends a fenced block at the first line holding at least as many
# backticks as the opener, indented by at most three spaces. A command carrying
# such a line — a heredoc, say — would close the block early and spill the rest
# of itself out as Markdown, where it reads as prose instead of as what runs.
_MIN_FENCE_LENGTH = 3
_BACKTICK_RUN = re.compile(r" {0,3}(`+)")


async def shell_formatter(
    ui: "AnyAgentOutput",
    call: "ToolCallPart",
    args_section: str,
) -> str | None:
    """Show a `Shell` call: its description, its fenced command, other flags."""
    if call.tool_name != "Shell":
        return None

    args = parse_tool_args(call)
    if args is None:
        return None

    command = args.get("command")
    if not isinstance(command, str) or not command:
        return None

    return _format_shell(command, args)


def _format_shell(command: str, args: Mapping[str, object]) -> str:
    lines: list[str] = []
    description = _flatten_description(args.get("description"))
    if description:
        lines.append(f"📝 {description}")
    command = _escape_unprintable(command, keep="\n\t")
    fence = _code_fence(command)
    lines.append(f"{fence}{_shell_fence(args.get('shell'))}")
    lines.extend(command.splitlines())
    lines.append(fence)
    section = render_indented_markdown("\n".join(lines))
    flags = _format_flags(args)
    return f"{section}\n{flags}" if flags else f"{section}\n"


def _escape_unprintable(text: object, keep: str = "") -> str:
    """`text` as a string with every non-printable character as a visible escape.

    Terminals act on ESC sequences and Markdown on Unicode line breaks, so a raw
    one could clear or rewrite the approval, or show two commands where the
    shell runs one. Characters in `keep` (the `\\n` and `\\t` of a command)
    pass through.
    """
    return "".join(
        char
        if char in keep or char.isprintable()
        else char.encode("unicode_escape").decode()
        for char in str(text)
    )


def _code_fence(command: str) -> str:
    """A backtick run long enough that `command` cannot close the block."""
    runs = (
        len(match.group(1))
        for match in map(_BACKTICK_RUN.match, command.splitlines())
        if match
    )
    return "`" * max(_MIN_FENCE_LENGTH, max(runs, default=0) + 1)


def _flatten_description(description: object) -> str:
    """The description on one line: one spread over lines could fence itself."""
    if not isinstance(description, str):
        return ""
    return _escape_unprintable(" ".join(description.split()))


def _shell_fence(shell_arg: object) -> str:
    """The fence language for the shell `shell_arg` names; empty means default."""
    if not isinstance(shell_arg, str):
        shell_arg = ""
    resolved_shell, _flag = resolve_shell(shell_arg)
    return _SHELL_FENCES.get(get_shell_name(resolved_shell), "")


def _format_flags(args: Mapping[str, object]) -> str:
    """Every argument that departs from its default, on one line."""
    flags: list[str] = []
    if args.get("cwd"):
        flags.append(f"cwd={_escape_unprintable(args['cwd'])}")
    if args.get("timeout", _DEFAULT_TIMEOUT) != _DEFAULT_TIMEOUT:
        flags.append(f"timeout={_escape_unprintable(args['timeout'])}s")
    if args.get("max_chars", _DEFAULT_MAX_CHARS) != _DEFAULT_MAX_CHARS:
        flags.append(f"max_chars={_escape_unprintable(args['max_chars'])}")
    if args.get("shell"):
        flags.append(f"shell={_escape_unprintable(args['shell'])}")
    if args.get("background"):
        flags.append("background")
    if args.get("dangerously_skip_sandbox"):
        flags.append("⚠ NO SANDBOX")
    if not flags:
        return ""
    return "       ⚙ " + " · ".join(flags) + "\n"
