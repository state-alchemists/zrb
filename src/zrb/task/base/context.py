import os
from typing import TYPE_CHECKING

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask

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
    task: AnyTask, shared_context: AnySharedContext, str_kwargs: dict[str, str] = {}
):
    """
    Populates the shared context with input values provided via kwargs.
    """
    for task_input in task.inputs:
        if task_input.name not in shared_context.input:
            str_value = str_kwargs.get(task_input.name, None)
            task_input.update_shared_context(shared_context, str_value)


def fill_shared_context_envs(shared_context: AnySharedContext):
    """
    Injects OS environment variables into the shared context if they don't already exist.
    """
    os_env_map = {
        key: val for key, val in os.environ.items() if key not in shared_context.env
    }
    shared_context.env.update(os_env_map)


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


def get_combined_envs(task: "BaseTask") -> list[AnyEnv]:
    """
    Aggregates environment variables from the task and its upstreams.
    """
    envs = []
    for upstream in task.upstreams:
        envs.extend(upstream.envs)  # Use extend for list concatenation

    # Access _envs directly as task is BaseTask
    task_envs: list[AnyEnv | None] | AnyEnv | None = task._envs
    if isinstance(task_envs, AnyEnv):
        envs.append(task_envs)
    elif isinstance(task_envs, list):
        # Filter out None while extending
        envs.extend(env for env in task_envs if env is not None)

    # Filter out None values efficiently from the combined list
    return [env for env in envs if env is not None]


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
