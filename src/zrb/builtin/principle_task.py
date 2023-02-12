from typing import Any
from ._group import principle_show_group
from ..task.task import Task
from ..runner import runner

# Common definitions


def _principle_show_solid(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('S - Single Responsibility Principle')
    task.print_out('O - Open/Closed Principle')
    task.print_out('L - Liskov’s Substitution Principle')
    task.print_out('I - Interface Segregation Principle')
    task.print_out('D - Dependency Inversion Principle')


def _principle_show_yagni(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('Y - You')
    task.print_out('A - Aren\'t')
    task.print_out('G - Gonna')
    task.print_out('N - Need')
    task.print_out('I - It')


def _principle_show_dry(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('D - Don\'t')
    task.print_out('R - Repeat')
    task.print_out('Y - Yourself')


def _principle_show_kiss(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('K - Keep')
    task.print_out('I - It')
    task.print_out('S - Simple')
    task.print_out('S - Stupid')


def _principle_show_pancasila(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('1. Ketuhanan Yang Maha Esa')
    task.print_out('2. Kemanusiaan yang adil dan beradab')
    task.print_out('3. Persatuan Indonesia')
    task.print_out(' '.join([
        '4. Kerakyatan yang dipimpin oleh hikmat kebijaksanaan',
        'dalam permusyawaratan/perwakilan'
    ]))
    task.print_out('5. Keadilan sosial bagi seluruh rakyat Indonesia')


# Task definitions

principle_show_solid_task = Task(
    name='solid',
    group=principle_show_group,
    run=_principle_show_solid,
    description='Show SOLID principle',
)
runner.register(principle_show_solid_task)

principle_show_yagni_task = Task(
    name='yagni',
    group=principle_show_group,
    run=_principle_show_yagni,
    description='Show YAGNI principle',
)
runner.register(principle_show_yagni_task)

principle_show_dry_task = Task(
    name='dry',
    group=principle_show_group,
    run=_principle_show_dry,
    description='Show dry principle',
)
runner.register(principle_show_dry_task)

principle_show_kiss_task = Task(
    name='kiss',
    group=principle_show_group,
    run=_principle_show_kiss,
    description='Show kiss principle',
)
runner.register(principle_show_kiss_task)

principle_show_pancasila_task = Task(
    icon="🦅",
    name='pancasila',
    group=principle_show_group,
    run=_principle_show_pancasila,
    description='Show pancasila',
)
runner.register(principle_show_pancasila_task)
