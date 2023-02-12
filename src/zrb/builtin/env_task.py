from typing import Any, Mapping
from ._group import env_group
from ..helper.accessories.color import colored
from ..task.task import Task
from ..runner import runner

import os

# Common definitions


def _env_show(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    env_map = task.get_env_map()
    names = list(env_map.keys())
    names.sort()
    for name in names:
        value = os.getenv(name)
        colored_name = colored(name, color='green', attrs=['bold'])
        colored_equal = colored('=', color='grey', attrs=['dark'])
        colored_value = colored(value, attrs=['bold'])
        task.print_out(f'{colored_name}{colored_equal}{colored_value}')


def _env_get(*args: Any, **kwargs: Any) -> Mapping[str, str]:
    task: Task = kwargs['_task']
    return task.get_env_map()


# Task definitions

env_show_task = Task(
    name='show',
    group=env_group,
    run=_env_show,
    description='Show environment values'
)
runner.register(env_show_task)

env_get_task = Task(
    name='get',
    group=env_group,
    run=_env_get,
    description='Get environment values'
)
runner.register(env_get_task)
