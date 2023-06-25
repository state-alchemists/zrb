from typing import Any, Mapping
from ._group import env_group
from ..helper.accessories.color import colored
from ..task.decorator import python_task
from ..task.task import Task
from ..runner import runner

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='get',
    group=env_group,
    description='Get environment values',
    runner=runner
)
async def get(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    env_map = task.get_env_map()
    names = list(env_map.keys())
    names.sort()
    colored_equal = colored('=', color='grey', attrs=['dark'])
    for name in names:
        value = env_map[name]
        colored_name = colored(name, color='green', attrs=['bold'])
        colored_value = colored(value, attrs=['bold'])
        task.print_out(f'{colored_name}{colored_equal}{colored_value}')
    return env_map
