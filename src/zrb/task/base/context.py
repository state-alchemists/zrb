import os
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.string.conversion import to_snake_case

if TYPE_CHECKING:
    # Keep BaseTask under TYPE_CHECKING for functions that need it
    from zrb.task.base_task import BaseTask


def build_task_context(task: AnyTask, session: AnySession) -> AnyContext:
    """
    Retrieves the context for the task from the session and enhances it
    with the task's specific environment variables.
    """
    ctx = session.get_ctx(task)
    # Enhance session ctx with current task env
    for env in task.envs:
        env.update_context(ctx)
    return ctx


def fill_shared_context_inputs(
    shared_ctx: AnySharedContext,
    task: AnyTask,
    str_kwargs: dict[str, str] | None = None,
    kwargs: dict[str, Any] | None = None,
):
    """
    Populates the shared context with input values provided via str_kwargs.
    """
    str_kwarg_dict = str_kwargs if str_kwargs is not None else {}
    kwarg_dict = kwargs if kwargs is not None else {}
    for task_input in task.inputs:
        if task_input.name not in shared_ctx.input:
            val = kwarg_dict.get(task_input.name, None)
            if val is None:
                val = kwarg_dict.get(to_snake_case(task_input.name), None)
            task_input.update_shared_context(
                shared_ctx,
                value=val,
                str_value=str_kwarg_dict.get(task_input.name, None),
            )


def fill_shared_context_envs(shared_ctx: AnySharedContext):
    """
    Injects OS environment variables into the shared context if they don't already exist.
    """
    os_env_map = {
        key: val for key, val in os.environ.items() if key not in shared_ctx.env
    }
    shared_ctx.env.update(os_env_map)


def combine_inputs(
    existing_inputs: list[AnyInput],
    new_inputs: list[AnyInput | None] | AnyInput | None,
):
    """
    Combines new inputs into an existing list, avoiding duplicates by name.
    Modifies the existing_inputs list in place.
    """
    input_names = [task_input.name for task_input in existing_inputs]
    if isinstance(new_inputs, AnyInput):
        new_inputs_list = [new_inputs]
    elif new_inputs is None:
        new_inputs_list = []
    else:
        new_inputs_list = new_inputs

    for task_input in new_inputs_list:
        if task_input is None:
            continue
        if task_input.name not in input_names:
            existing_inputs.append(task_input)
            input_names.append(task_input.name)  # Update names list


def combine_envs(
    existing_envs: list[AnyEnv],
    new_envs: list[AnyEnv | None] | AnyEnv | None,
):
    """
    Combines new envs into an existing list.
    Modifies the existing_envs list in place.
    """
    if isinstance(new_envs, AnyEnv):
        existing_envs.append(new_envs)
    elif new_envs is None:
        pass
    else:
        # new_envs is a list
        for env in new_envs:
            if env is not None:
                existing_envs.append(env)


def get_combined_envs(task: "BaseTask") -> list[AnyEnv]:
    """
    Aggregates environment variables from the task and its upstreams.
    """
    envs: list[AnyEnv] = []
    for upstream in task.upstreams:
        combine_envs(envs, upstream.envs)

    combine_envs(envs, task._envs)

    return envs


def get_combined_inputs(task: "BaseTask") -> list[AnyInput]:
    """
    Aggregates inputs from the task and its upstreams, avoiding duplicates.
    """
    inputs: list[AnyInput] = []
    for upstream in task.upstreams:
        combine_inputs(inputs, upstream.inputs)

    # Access _inputs directly as task is BaseTask
    task_inputs: list[AnyInput | None] | AnyInput | None = task._inputs
    if task_inputs is not None:
        combine_inputs(inputs, task_inputs)

    # Filter out None values (although combine_inputs should handle this)
    return [task_input for task_input in inputs if task_input is not None]
