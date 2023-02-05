from typing import Any
from ._group import show_principle
from ..task.task import Task
from ..runner import runner

# show solid principle
show_solid_principle = Task(
    name='solid',
    group=show_principle,
    description='Show SOLID principle',
)
runner.register(show_solid_principle)


@show_solid_principle.runner
def run_show_solid_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('S - Single Responsibility Principle')
    task.print_out('O - Open/Closed Principle')
    task.print_out('L - Liskov’s Substitution Principle')
    task.print_out('I - Interface Segregation Principle')
    task.print_out('D - Dependency Inversion Principle')


# show yagni principle
show_yagni_principle = Task(
    name='yagni',
    group=show_principle,
    description='Show YAGNI principle',
)
runner.register(show_yagni_principle)


@show_yagni_principle.runner
def run_show_yagni_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('Y - You')
    task.print_out('A - Aren\'t')
    task.print_out('G - Gonna')
    task.print_out('N - Need')
    task.print_out('I - It')


# show dry principle
show_dry_principle = Task(
    name='dry',
    group=show_principle,
    description='Show dry principle',
)
runner.register(show_dry_principle)


@show_dry_principle.runner
def run_show_dry_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('D - Don\'t')
    task.print_out('R - Repeat')
    task.print_out('Y - Yourself')


# show kiss principle
show_kiss_principle = Task(
    name='kiss',
    group=show_principle,
    description='Show kiss principle',
)
runner.register(show_kiss_principle)


@show_kiss_principle.runner
def run_show_kiss_principle(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('K - Keep')
    task.print_out('I - It')
    task.print_out('S - Simple')
    task.print_out('S - Stupid')


# show pancasila
show_pancasila = Task(
    name='pancasila',
    group=show_principle,
    description='Show pancasila',
)
runner.register(show_pancasila)


@show_pancasila.runner
def run_show_pancasila(*args: Any, **kwargs: Any):
    task: Task = kwargs['_task']
    task.print_out('1. Ketuhanan Yang Maha Esa')
    task.print_out('2. Kemanusiaan yang adil dan beradab')
    task.print_out('3. Persatuan Indonesia')
    task.print_out(' '.join([
        '4. Kerakyatan yang dipimpin oleh hikmat kebijaksanaan',
        'dalam permusyawaratan/perwakilan'
    ]))
    task.print_out('5. Keadilan sosial bagi seluruh rakyat Indonesia')
