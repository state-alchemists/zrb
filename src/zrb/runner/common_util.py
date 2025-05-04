from typing import Any

from zrb.context.shared_context import SharedContext
from zrb.task.any_task import AnyTask


def get_run_kwargs(
    task: AnyTask, args: list[str], kwargs: dict[str, str], cli_mode: bool
) -> dict[str, str]:
    arg_index = 0
    str_kwargs = {key: f"{val}" for key, val in kwargs.items()}
    run_kwargs = {**str_kwargs}
    shared_ctx = SharedContext(args=args)
    for task_input in task.inputs:
        if task_input.name in str_kwargs:
            # Update shared context for next input default value
            task_input.update_shared_context(shared_ctx, str_kwargs[task_input.name])
        elif arg_index < len(args) and task_input.allow_positional_parsing:
            run_kwargs[task_input.name] = args[arg_index]
            # Update shared context for next input default value
            task_input.update_shared_context(shared_ctx, run_kwargs[task_input.name])
            arg_index += 1
        else:
            if cli_mode and task_input.always_prompt:
                str_value = task_input.prompt_cli_str(shared_ctx)
            else:
                str_value = task_input.get_default_str(shared_ctx)
            run_kwargs[task_input.name] = str_value
            # Update shared context for next input default value
            task_input.update_shared_context(shared_ctx, run_kwargs[task_input.name])
    return run_kwargs
