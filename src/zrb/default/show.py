from typing import Any
from ..helper.accessories.color import colored
from ..task.cmd_task import CmdTask
from ..task.task import Task
from ..task_group.group import Group
from ..runner import runner

import os


show_group = Group(name='show', description='Show things')

show_solid_principle = CmdTask(
    name='solid-principle',
    group=show_group,
    description='Show SOLID principle',
    cmd=[
        'echo S - Single Responsibility Principle',
        'echo O - Open/Closed Principle',
        'echo L - Liskov’s Substitution Principle',
        'echo I - Interface Segregation Principle',
        'echo D - Dependency Inversion Principle'
    ]
)
runner.register(show_solid_principle)

show_env = Task(
    name='env',
    group=show_group,
    description='Show environment values'
)
runner.register(show_env)


@show_env.runner
def show_env(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    for name, value in os.environ.items():
        colored_name = colored(name, color='green', attrs=['bold'])
        colored_equal = colored('=', color='grey', attrs=['dark'])
        colored_value = colored(value, attrs=['bold'])
        task.print_out(f'{colored_name}{colored_equal}{colored_value}')
