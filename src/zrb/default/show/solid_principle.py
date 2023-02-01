from ._group import show_group
from ...task.cmd_task import CmdTask

show_solid_principle = CmdTask(
    name='solid-principle',
    group=show_group,
    cmd=[
        'echo S - Single Responsibility Principle',
        'echo O - Open/Closed Principle',
        'echo L - Liskov’s Substitution Principle',
        'echo I - Interface Segregation Principle',
        'echo D - Dependency Inversion Principle'
    ]
)
