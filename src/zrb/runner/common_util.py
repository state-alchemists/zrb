from zrb.context.shared_context import SharedContext
from zrb.task.any_task import AnyTask
from zrb.util.string.suggestion import format_suggestion


def get_task_str_kwargs(
    task: AnyTask, str_args: list[str], str_kwargs: dict[str, str], cli_mode: bool
) -> dict[str, str]:
    if cli_mode:
        _reject_unknown_kwargs(task, str_kwargs)
    arg_index = 0
    # Each resolved value feeds later inputs' defaults.
    dummy_shared_ctx = SharedContext()
    task_str_kwargs = {}
    for task_input in task.inputs:
        input_name = task_input.name
        if input_name in str_kwargs:
            str_value = str_kwargs[input_name]
        elif arg_index < len(str_args) and task_input.allow_positional_parsing:
            str_value = str_args[arg_index]
            arg_index += 1
        elif cli_mode and task_input.always_prompt:
            str_value = task_input.prompt_cli_str(dummy_shared_ctx)
        else:
            str_value = task_input.get_default_str(dummy_shared_ctx)
        task_str_kwargs[input_name] = str_value
        task_input.update_shared_context(dummy_shared_ctx, str_value=str_value)
    return task_str_kwargs


# Flags the CLI consumes before a task sees them.
_CLI_RESERVED_KWARGS = frozenset(("h", "help"))


def _reject_unknown_kwargs(task: AnyTask, str_kwargs: dict[str, str]) -> None:
    """Fail on a `--flag` no input of `task` declares.

    Only keyword arguments are checked; leftover positionals become `ctx.args`.
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
