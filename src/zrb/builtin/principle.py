from typing import Any
from ._group import principle_show_group
from ..task.decorator import python_task
from ..task.task import Task
from ..runner import runner


@python_task(
    name='solid',
    group=principle_show_group,
    description='Show SOLID principle',
    runner=runner
)
def show_solid_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('S - Single Responsibility Principle')
    task.print_out('O - Open/Closed Principle')
    task.print_out('L - Liskov’s Substitution Principle')
    task.print_out('I - Interface Segregation Principle')
    task.print_out('D - Dependency Inversion Principle')


@python_task(
    name='yagni',
    group=principle_show_group,
    description='Show YAGNI principle',
    runner=runner
)
def show_yagni_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('Y - You')
    task.print_out('A - Aren\'t')
    task.print_out('G - Gonna')
    task.print_out('N - Need')
    task.print_out('I - It')


@python_task(
    name='dry',
    group=principle_show_group,
    description='Show dry principle',
    runner=runner
)
def show_dry_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('D - Don\'t')
    task.print_out('R - Repeat')
    task.print_out('Y - Yourself')


@python_task(
    name='kiss',
    group=principle_show_group,
    description='Show kiss principle',
    runner=runner
)
def show_kiss_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('K - Keep')
    task.print_out('I - It')
    task.print_out('S - Simple')
    task.print_out('S - Stupid')
