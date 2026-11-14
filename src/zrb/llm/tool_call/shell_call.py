"""What a `Shell` call is, and where its command lives — known once.

A deferred `ToolCallPart` offers one handle on what the model asked for: the
tool's name. It carries no capability tag, because the tag lives on the
registered callable, so every part of the run that has to recognise a shell
command compares the name itself. Three did — the approval formatter, the
read-only auto-approve policy and the shell judge — and each then reached into
the arguments for the command and the sandbox flag on its own, which is three
readings of one shape and three places to update when it moves.

This module is that shape, once: the tool's runtime name, the argument that
carries the command, and the two questions every caller asks of a call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart

#: The runtime name of the shell tool (`tool/shell/command.py` registers it).
SHELL_TOOL_NAME = "Shell"
#: The argument holding the command text.
COMMAND_ARG = "command"
#: The argument asking to run outside the sandbox; always a human's decision.
NO_SANDBOX_ARG = "dangerously_skip_sandbox"


def is_shell_call(call: "ToolCallPart") -> bool:
    """Whether *call* asks for the shell tool, by name."""
    return getattr(call, "tool_name", None) == SHELL_TOOL_NAME


def shell_command_args(call: "ToolCallPart") -> dict[str, object] | None:
    """*call*'s parsed arguments when it runs a shell command, else `None`.

    `None` covers the cases every caller treats alike: another tool, a payload
    that is not an object, and a `command` that is absent, empty or blank.
    Returned as the whole dict rather than as the command string, so a caller
    that also wants the working directory or the sandbox flag does not parse
    the same payload twice.
    """
    # lazy: heavy third-party
    from zrb.llm.util.tool_args import parse_tool_args

    if not is_shell_call(call):
        return None
    args = parse_tool_args(call)
    if not isinstance(args, dict):
        return None
    command = args.get(COMMAND_ARG)
    if not isinstance(command, str) or not command.strip():
        return None
    return args


def shell_command(args: dict[str, object]) -> str:
    """The command in *args*, which `shell_command_args` guarantees is a string."""
    return str(args[COMMAND_ARG])


def is_sandbox_off(args: dict[str, object]) -> bool:
    """Whether *args* ask to run outside the sandbox."""
    return bool(args.get(NO_SANDBOX_ARG))


__all__ = [
    "COMMAND_ARG",
    "NO_SANDBOX_ARG",
    "SHELL_TOOL_NAME",
    "is_sandbox_off",
    "is_shell_call",
    "shell_command",
    "shell_command_args",
]
