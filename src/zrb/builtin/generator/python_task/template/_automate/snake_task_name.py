from typing import Any, Mapping
from zrb import (
    Task, runner
)
from zrb.builtin._group import project_group


def _snake_task_name(*args: Any, **kwargs: Any) -> Any:
    task: Task = kwargs.get('_task')
    env_map: Mapping[str, str] = task.get_env_map()
    input_map: Mapping[str, str] = task.get_input_map()
    task.print_out(f'Env map: {env_map}')
    task.print_out(f'Input map: {input_map}')
    return 'ok'


snake_task_name = Task(
    name='kebab-task-name',
    description='human readable task name',
    group=project_group,
    run=_snake_task_name
)
runner.register(snake_task_name)
