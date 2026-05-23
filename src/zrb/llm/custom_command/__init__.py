import shlex
from collections.abc import Callable

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.custom_command.custom_command import CustomCommand
from zrb.llm.custom_command.skill_command_factory import get_skill_custom_command

__all__ = [
    "AnyCustomCommand",
    "CustomCommand",
    "get_skill_custom_command",
    "resolve_custom_command",
    "resolve_custom_commands",
]


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


def resolve_custom_command(
    message: str,
    custom_commands: list[AnyCustomCommand],
) -> str | None:
    """If *message* starts with a registered custom command, resolve its prompt.

    Returns the transformed prompt string on match, or ``None`` if no
    registered command matched.
    """
    if not message.startswith("/"):
        return None

    try:
        parts = shlex.split(message.strip())
    except Exception:
        return None

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
            return custom_cmd.get_prompt(args_dict)
    return None
