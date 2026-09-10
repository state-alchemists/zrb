from zrb.context.shared_context import SharedContext
from zrb.task.any_task import AnyTask
from zrb.util.string.suggestion import format_suggestion


def get_task_str_kwargs(
    task: AnyTask, str_args: list[str], str_kwargs: dict[str, str], cli_mode: bool
) -> dict[str, str]:
    if cli_mode:
        _reject_unknown_kwargs(task, str_kwargs)
    arg_index = 0
    dummmy_shared_ctx = SharedContext()
    task_str_kwargs = {}
    for task_input in task.inputs:
        task_name = task_input.name
        if task_input.name in str_kwargs:
            task_str_kwargs[task_input.name] = str_kwargs[task_name]
            # Update dummy shared context for next input default value
            task_input.update_shared_context(
                dummmy_shared_ctx, str_value=str_kwargs[task_name]
            )
        elif arg_index < len(str_args) and task_input.allow_positional_parsing:
            task_str_kwargs[task_name] = str_args[arg_index]
            # Update dummy shared context for next input default value
            task_input.update_shared_context(
                dummmy_shared_ctx, str_value=task_str_kwargs[task_name]
            )
            arg_index += 1
        else:
            if cli_mode and task_input.always_prompt:
                str_value = task_input.prompt_cli_str(dummmy_shared_ctx)
            else:
                str_value = task_input.get_default_str(dummmy_shared_ctx)
            task_str_kwargs[task_name] = str_value
            # Update dummy shared context for next input default value
            task_input.update_shared_context(
                dummmy_shared_ctx, str_value=task_str_kwargs[task_name]
            )
    return task_str_kwargs


# Flags the CLI consumes before a task ever sees them. Listed here so a
# `--help` that reaches this function (a caller other than `Cli.run`) is not
# reported as an unknown option.
_CLI_RESERVED_KWARGS = frozenset(("h", "help"))


def _reject_unknown_kwargs(task: AnyTask, str_kwargs: dict[str, str]) -> None:
    """Fail on a `--flag` no input of `task` declares.

    The loop below only ever *reads* keys matching an input name, so without
    this an unrecognized option is indistinguishable from an absent one: the
    input it was meant for silently falls back to its default or an
    interactive prompt, and the task runs with values nobody asked for.

    Only keyword arguments are checked. Leftover positionals are passed on to
    the task as `ctx.args`, so an unconsumed one is legitimate input rather
    than a typo.
    """
    known = {task_input.name for task_input in task.inputs}
    unknown = [
        key
        for key in str_kwargs
        if key not in known and key not in _CLI_RESERVED_KWARGS
    ]
    if not unknown:
        return
    sorted_known = sorted(known)
    details = ", ".join(
        f"'--{key}'{format_suggestion(key, sorted_known)}" for key in sorted(unknown)
    )
    known_str = (
        ", ".join(f"--{name}" for name in sorted_known)
        if sorted_known
        else "(this task takes no options)"
    )
    raise ValueError(
        f"Unknown option for task '{task.name}': {details} Available: {known_str}"
    )
