from typing import Any, Mapping
from ._group import show, get
from ..helper.accessories.color import colored
from ..task.task import Task
from ..runner import runner

import os


# show env
show_env = Task(
    name='env',
    group=show,
    description='Show environment values'
)
runner.register(show_env)


@show_env.runner
def run_show_env(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    for name, value in os.environ.items():
        colored_name = colored(name, color='green', attrs=['bold'])
        colored_equal = colored('=', color='grey', attrs=['dark'])
        colored_value = colored(value, attrs=['bold'])
        task.print_out(f'{colored_name}{colored_equal}{colored_value}')


# get env
get_env = Task(
    name='env',
    group=get,
    description='get environment values'
)
runner.register(get_env)


@get_env.runner
def run_get_env(*args: Any, **kwargs: Any) -> Mapping[str, str]:
    return dict(os.environ)
