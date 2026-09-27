import shlex
from collections.abc import Callable
from typing import NamedTuple

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand


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
    """If *message* starts with a registered custom command, resolve its prompt.

    Returns the transformed prompt string on match, or ``None`` if no
    registered command matched. Never runs ``handle``; see
    `run_custom_command` for callers that should.
    """
    match = get_custom_command_match(message, custom_commands)
    if match is None:
        return None
    custom_cmd, kwargs = match
    return custom_cmd.get_prompt(kwargs)


def run_custom_command(
    message: str,
    custom_commands: list[AnyCustomCommand],
) -> CustomCommandOutcome | None:
    """Run the custom command *message* names, or return ``None`` if none matches.

    The command's ``handle`` runs first; only when it declines (returns
    ``None``) is ``get_prompt`` resolved for the LLM.
    """
    match = get_custom_command_match(message, custom_commands)
    if match is None:
        return None
    custom_cmd, kwargs = match
    # getattr: duck-typed commands written before `handle` existed lack it.
    handle = getattr(custom_cmd, "handle", None)
    reply = handle(kwargs) if handle is not None else None
    if reply is not None:
        return CustomCommandOutcome(prompt=None, reply=reply)
    return CustomCommandOutcome(prompt=custom_cmd.get_prompt(kwargs), reply=None)


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
