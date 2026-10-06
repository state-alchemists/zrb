from __future__ import annotations

import inspect
import shlex
from collections.abc import Callable
from inspect import Parameter
from typing import TYPE_CHECKING, Any, NamedTuple

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


def resolve_custom_commands(
    raw_commands: list[
        AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
    ],
) -> list[AnyCustomCommand]:
    """Resolve custom command list, calling any callable factories."""
    resolved: list[AnyCustomCommand] = []
    for cmd in raw_commands:
        if callable(cmd):
            res = cmd()
            if isinstance(res, list):
                resolved.extend(res)
            else:
                resolved.append(res)
        else:
            resolved.append(cmd)
    return resolved


class CustomCommandOutcome(NamedTuple):
    """What a matched custom command produced: a prompt for the LLM, or a
    reply to show the user (``handle`` ran and no turn starts)."""

    prompt: str | None
    reply: str | None


def resolve_custom_command(
    message: str,
    custom_commands: list[AnyCustomCommand],
) -> str | None:
    """Resolve the prompt for the command named by *message*, if any."""
    match = get_custom_command_match(message, custom_commands)
    if match is None:
        return None
    custom_cmd, kwargs = match
    return custom_cmd.get_prompt(kwargs)


def run_custom_command(
    message: str,
    custom_commands: list[AnyCustomCommand],
    ui: "BaseUI | None",
) -> CustomCommandOutcome | None:
    """Run the command named by *message* and return its outcome."""
    match = get_custom_command_match(message, custom_commands)
    if match is None:
        return None
    custom_cmd, kwargs = match
    # getattr: duck-typed commands written before `handle` existed lack it.
    handle = getattr(custom_cmd, "handle", None)
    if handle is None:
        reply = None
    elif _can_take_ui(handle):
        reply = handle(kwargs, ui)
    else:
        reply = handle(kwargs)
    if reply is not None:
        return CustomCommandOutcome(prompt=None, reply=reply)
    return CustomCommandOutcome(prompt=custom_cmd.get_prompt(kwargs), reply=None)


def _can_take_ui(handle: "Callable[..., Any]") -> bool:
    """Whether *handle* accepts the optional ``ui`` argument."""
    try:
        parameters = inspect.signature(handle).parameters
    except (TypeError, ValueError):
        # Not introspectable (a C function, say): the current signature.
        return True
    if any(p.kind is Parameter.VAR_POSITIONAL for p in parameters.values()):
        return True
    positional = [
        p
        for p in parameters.values()
        if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2


def get_custom_command_match(
    message: str,
    custom_commands: list[AnyCustomCommand],
) -> tuple[AnyCustomCommand, dict[str, str]] | None:
    """The command *message* names and its parsed arguments, or ``None``."""
    if not message.startswith("/"):
        return None

    try:
        parts = shlex.split(message.strip())
    except ValueError:
        # Unbalanced quote (shlex's only failure mode here). Fall back to
        # whitespace splitting so `/my-command "oops` still dispatches to
        # `/my-command` instead of silently reaching the model as a plain
        # message, which reads to the user as the command being ignored.
        parts = message.strip().split()

    if not parts:
        return None

    cmd_name = parts[0]
    for custom_cmd in custom_commands:
        if cmd_name == custom_cmd.command:
            provided_args = parts[1:]
            # Join residue arguments if more provided than expected
            if len(provided_args) > len(custom_cmd.args):
                num_args = len(custom_cmd.args)
                if num_args > 0:
                    args_to_keep = provided_args[: num_args - 1]
                    residue = provided_args[num_args - 1 :]
                    provided_args = args_to_keep + [" ".join(residue)]

            args_dict = {
                custom_cmd.args[i]: (provided_args[i] if i < len(provided_args) else "")
                for i in range(len(custom_cmd.args))
            }
            return custom_cmd, args_dict
    return None
