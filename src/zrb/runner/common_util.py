from zrb.context.shared_context import SharedContext
from zrb.task.any_task import AnyTask


def get_task_str_kwargs(
    task: AnyTask, str_args: list[str], str_kwargs: dict[str, str], cli_mode: bool
) -> dict[str, str]:
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
